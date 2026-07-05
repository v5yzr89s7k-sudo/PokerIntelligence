from pathlib import Path
import json
import time
import subprocess
import cv2
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.events.detectors.action_buttons_detector import action_buttons_visible
from src.events.detectors.hero_turn_detector import hero_nameplate_blinking_rolling

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))

HERO_READER = ROOT / "src/api/hero_cards_api_reader.py"
BOARD_READER = ROOT / "src/api/board_api_reader.py"
SNAPSHOT_READER = ROOT / "src/api/table_snapshot_api_reader.py"

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
COORD_STATE = ROOT / "runtime/live/api_event_coordinator_state.json"
EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


def fresh_state():
    return {
        "phase": "WAITING",
        "hero_read": False,
        "confirmed_board_len": 0,
        "stable_board_count": 0,
        "stable_seen": 0,
        "last_api_attempt_ts": 0,
        "board_clear_seen": 0,
        "hero_clear_seen": 0,
        "hero_visible_seen": 0,
        "last_event": None,
        "hero_decision_active": False,
    }


def load_state():
    if COORD_STATE.exists():
        try:
            state = json.loads(COORD_STATE.read_text())
        except Exception:
            return fresh_state()

        base = fresh_state()
        for k, v in base.items():
            state.setdefault(k, v)
        return state

    return fresh_state()


def save_state(state):
    COORD_STATE.write_text(json.dumps(state, indent=2))


def emit(event):
    event["ts"] = time.time()
    EVENT_LOG.open("a").write(json.dumps(event) + "\n")
    print("[EVENT]", event)


def capture():
    subprocess.run(
        ["python3", str(CAPTURE)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    return latest_capture()


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    return files[-1] if files else None


def crop(img, r):
    x, y, w, h = map(int, [r["x"], r["y"], r["width"], r["height"]])
    return img[y:y+h, x:x+w]


def card_present(c):
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    return (gray > 145).mean() > 0.08


def local_board_count(path):
    if not path:
        return 0

    img = cv2.imread(str(path))
    if img is None:
        return 0

    img = cv2.resize(img, (934, 696))

    count = 0
    for _, r in GEOM.get("board", {}).items():
        if card_present(crop(img, r)):
            count += 1

    return count


def local_hero_cards_visible(path):
    if not path:
        return False

    img = cv2.imread(str(path))
    if img is None:
        return False

    img = cv2.resize(img, (934, 696))

    hero = GEOM.get("hero_cards") or GEOM.get("hole_cards", {}).get("hero", {})
    if not hero:
        return False

    seen = 0
    for _, r in hero.items():
        if card_present(crop(img, r)):
            seen += 1

    return seen >= 2


def run_json(script, frame=None):
    cmd = ["python3", str(script)]
    if frame:
        cmd.append(str(frame))

    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )

    if p.returncode != 0:
        print(f"[ERROR] {script.name} failed")
        print(p.stderr)
        return None

    text = p.stdout.strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        print(f"[ERROR] could not parse JSON from {script.name}")
        print(text)
        return None



def local_action_buttons_visible(path):
    if not path:
        return False

    img = cv2.imread(str(path))
    if img is None:
        return False

    img = cv2.resize(img, (934, 696))
    return action_buttons_visible(img, GEOM)


def local_hero_blink_visible():
    blink, max_diff, diffs = hero_nameplate_blinking_rolling(
        capture_fn=capture,
        latest_capture_fn=latest_capture,
        geometry=GEOM,
        samples=6,
        delay=0.18,
        threshold=5.0,
    )
    print(f"[HERO_BLINK] blink={blink} max_diff={max_diff:.2f} diffs={[round(d, 2) for d in diffs]}")
    return blink


def maybe_emit_hero_decision(state, visible, hero_visible):
    if state.get("phase") == "WAITING":
        state["hero_decision_active"] = False
        return state

    if visible:
        print(f"[HERO_DECISION_CHECK] visible={visible} hero_visible={hero_visible} phase={state.get('phase')} active={state.get('hero_decision_active')}")

    if visible and hero_visible and not state.get("hero_decision_active"):
        emit({"type": "hero_decision"})
        state["hero_decision_active"] = True
        return state

    if not visible and state.get("hero_decision_active"):
        emit({"type": "hero_action_complete"})
        state["hero_decision_active"] = False
        return state

    if not visible:
        state["hero_decision_active"] = False

    return state


def maybe_read_hero(state, hero_visible, board_count, frame):
    if state.get("phase") != "WAITING":
        return state

    if not hero_visible:
        return state

    if board_count != 0:
        print(f"[HERO] visible but board_count={board_count}; waiting for clean hand")
        state["hero_visible_seen"] = 0
        return state

    state["hero_visible_seen"] = state.get("hero_visible_seen", 0) + 1
    if state["hero_visible_seen"] < 2:
        print(f"[HERO] visible {state['hero_visible_seen']}/2")
        return state

    if state["hero_read"]:
        return state

    data = run_json(HERO_READER, frame)
    if not data:
        return state

    cards = data.get("hero_cards") or []
    if len(cards) == 2:
        state["hero_read"] = True
        state["phase"] = "PREFLOP"
        state["hero_clear_seen"] = 0
        emit({"type": "hero_cards", "hero_cards": cards})

        snapshot = run_json(SNAPSHOT_READER, frame)
        if snapshot:
            emit({
                "type": "table_snapshot",
                "players": snapshot.get("players") or [],
                "hero_position": snapshot.get("hero_position") or "unknown",
                "dealer_button_seat": snapshot.get("dealer_button_seat") or "",
                "confidence": snapshot.get("confidence"),
            })

    return state


def maybe_read_board(state, count, frame):
    if state.get("phase") == "WAITING":
        return state

    confirmed = state["confirmed_board_len"]

    if count not in (3, 4, 5):
        return state

    if count <= confirmed:
        return state

    now = time.time()
    last_attempt = state.get("last_api_attempt_ts", 0)

    # Do not spam API while waiting for the visual/API state to catch up.
    if now - last_attempt < 1.25:
        print(f"[BOARD] local_count={count} confirmed={confirmed}; cooldown")
        return state

    state["last_api_attempt_ts"] = now
    print(f"[BOARD] local_count={count} confirmed={confirmed}; calling API")

    data = run_json(BOARD_READER, frame)
    if not data:
        return state

    board = data.get("board") or []

    if len(board) > confirmed:
        state["confirmed_board_len"] = len(board)
        if len(board) == 3:
            state["phase"] = "FLOP"
        elif len(board) == 4:
            state["phase"] = "TURN"
        elif len(board) == 5:
            state["phase"] = "RIVER"
        emit({"type": "board", "board": board})
    else:
        print(f"[BOARD] API returned len={len(board)} confirmed={confirmed}; will retry")

    return state



def maybe_complete_early(state, count, hero_visible):
    phase = state.get("phase")

    if phase == "WAITING":
        state["hero_clear_seen"] = 0
        return state

    # If hero cards disappear, hero is out of the hand or the hand has ended.
    if not hero_visible:
        state["hero_clear_seen"] = state.get("hero_clear_seen", 0) + 1
        print(f"[HAND] hero cards not visible {state['hero_clear_seen']}/4")
    else:
        state["hero_clear_seen"] = 0

    if state["hero_clear_seen"] >= 4:
        emit({"type": "hand_complete", "result": "Hero cards cleared / hero folded or hand ended"})
        return fresh_state()

    # If board clears after any street, the hand ended before showdown/river completion.
    if phase in ("FLOP", "TURN") and count == 0:
        state["board_clear_seen"] = state.get("board_clear_seen", 0) + 1
        print(f"[HAND] board cleared before river {state['board_clear_seen']}/4")
        if state["board_clear_seen"] >= 4:
            emit({"type": "hand_complete", "result": "Board cleared before river"})
            return fresh_state()
    elif phase in ("FLOP", "TURN"):
        state["board_clear_seen"] = 0

    return state


def maybe_complete_hand(state, count):
    if state.get("phase") != "RIVER":
        state["board_clear_seen"] = 0
        return state

    if count == 0:
        state["board_clear_seen"] = state.get("board_clear_seen", 0) + 1
        print(f"[HAND] river complete; board clear seen {state['board_clear_seen']}/4")
    else:
        state["board_clear_seen"] = 0

    if state["board_clear_seen"] >= 4:
        emit({"type": "hand_complete", "result": "Board cleared after river"})
        return fresh_state()

    return state


def main():
    print("api_event_coordinator running event-only mode. Ctrl+C to stop.")
    print(f"Events: {EVENT_LOG}")
    state = load_state()

    while True:
        frame = capture()

        hero_visible = local_hero_cards_visible(frame)
        count = local_board_count(frame)
        buttons_visible = local_action_buttons_visible(frame)
        blink_visible = False
        if state.get("phase") != "WAITING" and hero_visible:
            blink_visible = local_hero_blink_visible()

        hero_turn_visible = blink_visible or buttons_visible

        state = maybe_read_hero(state, hero_visible, count, frame)
        state = maybe_emit_hero_decision(state, hero_turn_visible, hero_visible)
        state = maybe_read_board(state, count, frame)
        state = maybe_complete_early(state, count, hero_visible)
        state = maybe_complete_hand(state, count)

        save_state(state)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
