from pathlib import Path
import json
import cv2
import pytesseract
import subprocess
import time
import re
from datetime import datetime
from src.state.poker_state_validator import PokerStateValidator

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOMETRY = ROOT / "config/geometry.json"

LIVE_DIR = ROOT / "runtime/live"
HISTORY_DIR = ROOT / "runtime/history"
LIVE_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

LIVE_TXT = LIVE_DIR / "live_hand_state.txt"
LIVE_JSON = LIVE_DIR / "live_hand_state.json"
CHANGE_LOG = LIVE_DIR / "change_log.txt"

geometry = json.load(open(GEOMETRY))


def latest_capture():
    return sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]


def capture_table():
    subprocess.run(
        ["python3", str(CAPTURE_SCRIPT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    img = cv2.imread(str(latest_capture()))
    return cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)


def crop_region(img, region):
    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])
    return img[y:y+h, x:x+w]


def ocr_text(crop, psm=7):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)[1]
    return pytesseract.image_to_string(gray, config=f"--psm {psm}").strip()


def extract_number(text):
    text = text.replace(",", ".").replace("|", "1").replace("O", "0").replace("o", "0")
    m = re.search(r"\d+(?:\.\d+)?", text)
    return m.group(0) if m else ""


def read_pot(img):
    out = {}
    for name, region in geometry.get("pot_region", {}).items():
        raw = ocr_text(crop_region(img, region))
        num = extract_number(raw)
        if num:
            out[name] = num
    return out


def read_stacks(img):
    out = {}
    for seat, region in geometry.get("stack_regions", {}).items():
        raw = ocr_text(crop_region(img, region))
        num = extract_number(raw)
        if num:
            out[seat] = num
    return out


def read_bets(img):
    out = {}
    for seat, region in geometry.get("bet_regions", {}).items():
        raw = ocr_text(crop_region(img, region))
        num = extract_number(raw)
        if num:
            out[seat] = num
    return out


def card_present(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    total = crop.shape[0] * crop.shape[1]
    bright_ratio = (gray > 145).sum() / total
    red_ratio = (((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & (hsv[:, :, 1] > 40)).sum() / total
    return bright_ratio > 0.08 or red_ratio > 0.03


def read_board_count(img):
    count = 0
    present = []
    for name, region in geometry.get("board", {}).items():
        if card_present(crop_region(img, region)):
            count += 1
            present.append(name)
    return count, present


def read_hero_cards_present(img):
    present = []
    for name, region in geometry.get("hero_cards", {}).items():
        if card_present(crop_region(img, region)):
            present.append(name)
    return present


def street_from_board_count(n):
    if n >= 5:
        return "RIVER"
    if n == 4:
        return "TURN"
    if n == 3:
        return "FLOP"
    return "PREFLOP"


def write_outputs(state, events):
    lines = []
    lines.append("POKER INTELLIGENCE LIVE HAND STATE")
    lines.append("=" * 60)
    lines.append(f"Updated: {state['updated_at']}")
    lines.append(f"Frame: {state['frame']}")
    lines.append(f"Street: {state['street']}")
    lines.append("")

    lines.append("POT")
    lines.append("-" * 20)
    if state["pot"]:
        for k, v in state["pot"].items():
            lines.append(f"{k}: {v} BB")
    else:
        lines.append("not detected")
    lines.append("")

    lines.append("PLAYERS / STACKS")
    lines.append("-" * 20)
    if state["stacks"]:
        for seat, stack in state["stacks"].items():
            lines.append(f"{seat}: {stack} BB")
    else:
        lines.append("not detected")
    lines.append("")

    lines.append("CURRENT BETS")
    lines.append("-" * 20)
    if state["bets"]:
        for seat, bet in state["bets"].items():
            lines.append(f"{seat}: {bet} BB")
    else:
        lines.append("none detected")
    lines.append("")

    lines.append("VISIBLE CARDS")
    lines.append("-" * 20)
    lines.append(f"Hero card regions visible: {', '.join(state['hero_cards_present']) if state['hero_cards_present'] else 'none'}")
    lines.append(f"Board cards visible: {state['board_count']} ({', '.join(state['board_present']) if state['board_present'] else 'none'})")
    lines.append("")

    lines.append("EVENTS")
    lines.append("-" * 20)
    if events:
        lines.extend(events[-40:])
    else:
        lines.append("no events yet")
    lines.append("")

    LIVE_TXT.write_text("\n".join(lines))
    LIVE_JSON.write_text(json.dumps(state, indent=2))
    CHANGE_LOG.write_text("\n".join(events))


def archive_hand(events):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = HISTORY_DIR / f"hand_{ts}.txt"
    path.write_text("\n".join(events))
    return path


def main():
    print("=" * 60)
    print("Poker Intelligence Live Hand-Cycle Writer")
    print("=" * 60)
    print("ACR table must be open and visible.")
    print("Writing:")
    print(f"  {LIVE_TXT}")
    print(f"  {LIVE_JSON}")
    print(f"  {CHANGE_LOG}")
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    events = []
    validator = PokerStateValidator()
    last = {
        "street": None,
        "pot": {},
        "stacks": {},
        "bets": {},
        "hero_cards_present": [],
        "board_count": None,
    }

    frame = 0

    try:
        while True:
            frame += 1
            img = capture_table()

            pot = read_pot(img)
            stacks = read_stacks(img)
            bets = read_bets(img)
            board_count, board_present = read_board_count(img)
            hero_cards_present = read_hero_cards_present(img)
            street = street_from_board_count(board_count)

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            raw_state = {
                "updated_at": now,
                "frame": frame,
                "street": street,
                "pot": pot,
                "stacks": stacks,
                "bets": bets,
                "hero_cards_present": hero_cards_present,
                "board_count": board_count,
                "board_present": board_present,
                "recent_events": events[-40:],
            }

            state, validated_changes = validator.validate(raw_state)

            # Rebuild event stream from validated state changes only.
            if validated_changes["street_changed"]:
                events.append(f"{now} | VALID STREET -> {state['street']}")

            if validated_changes["board_changed"]:
                events.append(f"{now} | VALID BOARD COUNT -> {state['board_count']}")

            if validated_changes["hero_cards_changed"]:
                events.append(f"{now} | VALID HERO CARDS -> {state['hero_cards_present'] if state['hero_cards_present'] else 'none'}")

            if validated_changes["pot_changed"]:
                events.append(f"{now} | VALID POT -> {state['pot']}")

            if validated_changes["bets_changed"]:
                events.append(f"{now} | VALID BETS -> {state['bets'] if state['bets'] else 'none'}")

            for seat, change in validated_changes["stack_changes"].items():
                old_val, new_val = change
                if old_val == "NEW":
                    events.append(f"{now} | VALID STACK {seat}: {new_val} BB")
                else:
                    events.append(f"{now} | VALID STACK {seat}: {old_val} BB -> {new_val} BB")

            state["recent_events"] = events[-40:]
            write_outputs(state, events)

            if frame % 10 == 0:
                print(f"Frame {frame}: street={street}, pot={pot}, stacks={len(stacks)}, bets={bets}")

            time.sleep(0.4)

    except KeyboardInterrupt:
        print()
        archive = archive_hand(events)
        print(f"Stopped. Archived event log to {archive}")


if __name__ == "__main__":
    main()
