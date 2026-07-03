from pathlib import Path
import json
import time
import subprocess
import cv2
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.events.local_event_detector import LocalEventDetector

ROOT = Path(__file__).resolve().parents[2]

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))

HERO_READER = ROOT / "src/api/hero_cards_api_reader.py"
BOARD_READER = ROOT / "src/api/board_api_reader.py"
TABLE_SNAPSHOT_READER = ROOT / "src/api/table_snapshot_api_reader.py"

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
COORD_STATE = ROOT / "runtime/live/api_event_coordinator_state.json"
EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)



SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]

def compute_hero_position(players, dealer_button_seat):
    # Position is based on occupied/dealt seats, not current active/folded status.
    occupied = [
        p.get("seat")
        for p in players
        if p.get("seat") in SEAT_ORDER
        and (p.get("name") or p.get("stack_bb") is not None or p.get("stack_text"))
    ]
    occupied = [s for s in SEAT_ORDER if s in occupied]

    if "hero" not in occupied or dealer_button_seat not in occupied:
        return "unknown"

    n = len(occupied)
    btn_i = occupied.index(dealer_button_seat)
    hero_i = occupied.index("hero")

    order = []
    for k in range(n):
        order.append(occupied[(btn_i + k) % n])

    if n == 2:
        labels = ["BTN/SB", "BB"]
    elif n == 3:
        labels = ["BTN", "SB", "BB"]
    elif n == 4:
        labels = ["BTN", "SB", "BB", "CO"]
    elif n == 5:
        labels = ["BTN", "SB", "BB", "UTG", "CO"]
    elif n == 6:
        labels = ["BTN", "SB", "BB", "UTG", "HJ", "CO"]
    elif n == 7:
        labels = ["BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"]
    else:
        labels = ["BTN", "SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO"]

    return labels[order.index("hero")]


def fresh_state():
    return {
        "phase": "WAITING",
        "hero_read": False,
        "table_snapshot_read": False,
        "confirmed_board_len": 0,
        "stable_board_count": 0,
        "stable_seen": 0,
        "last_api_attempt_ts": 0,
        "board_clear_seen": 0,
        "hero_clear_seen": 0,
        "hero_visible_seen": 0,
        "last_event": None,
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


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    return files[-1] if files else None



def run_json(script):
    p = subprocess.run(
        ["python3", str(script)],
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


def maybe_read_hero(state, hero_visible):
    if state.get("phase") != "WAITING":
        return state

    if not hero_visible:
        return state

    state["hero_visible_seen"] = state.get("hero_visible_seen", 0) + 1
    if state["hero_visible_seen"] < 2:
        print(f"[HERO] visible {state['hero_visible_seen']}/2")
        return state

    if state["hero_read"]:
        return state

    data = run_json(HERO_READER)
    if not data:
        return state

    cards = data.get("hero_cards") or []
    if len(cards) == 2:
        state["hero_read"] = True
        state["phase"] = "PREFLOP"
        state["hero_clear_seen"] = 0
        emit({"type": "hero_cards", "hero_cards": cards})

    return state



def maybe_read_table_snapshot(state):
    if state.get("phase") == "WAITING":
        return state

    if state.get("table_snapshot_read"):
        return state

    data = run_json(TABLE_SNAPSHOT_READER)
    if not data:
        return state

    players = data.get("players") or []
    for p in players:
        p["is_hero"] = p.get("seat") == "hero"

    dealer_button_seat = data.get("dealer_button_seat") or ""
    hero_position = compute_hero_position(players, dealer_button_seat)

    state["table_snapshot_read"] = True
    emit({
        "type": "table_snapshot",
        "hero_position": hero_position,
        "dealer_button_seat": dealer_button_seat,
        "players": players,
        "confidence": data.get("confidence", 0.0),
    })

    return state


def maybe_read_board(state, count):
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

    data = run_json(BOARD_READER)
    if not data:
        return state

    board = data.get("board") or []

    # Accept any forward progress, but never accept fewer/equal cards.
    # Local detector can jump 3 -> 5; API may correctly return the missing turn first.
    if len(board) <= confirmed:
        print(f"[BOARD] rejected: detector={count} API={len(board)} confirmed={confirmed}")
        return state

    if len(board) not in (3, 4, 5):
        print(f"[BOARD] rejected invalid length: API={len(board)}")
        return state

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
    detector = LocalEventDetector()

    while True:
        capture()

        frame = cv2.imread(str(latest_capture()))
        changes = detector.detect(frame)

        hero_visible = changes.hero_cards_visible
        count = changes.board_count

        if any([
            changes.hero_changed,
            changes.board_changed,
            changes.pot_changed,
            changes.dealer_changed,
            changes.action_buttons_changed,
            bool(changes.stack_changed_seats),
        ]):
            print("[LOCAL]", changes)

        state = maybe_read_hero(state, hero_visible)
        state = maybe_read_table_snapshot(state)
        state = maybe_read_board(state, count)
        state = maybe_complete_early(state, count, hero_visible)
        state = maybe_complete_hand(state, count)

        save_state(state)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
