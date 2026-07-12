from pathlib import Path
import json
import time
import subprocess
import cv2
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.events.detectors.action_buttons_detector import action_buttons_visible
from src.events.detectors.hero_turn_detector import hero_nameplate_blinking_rolling
from src.events.local_event_detector import LocalEventDetector
from src.observer.continuous_observer import ContinuousObserver
from src.observer.observation_timeline import ObservationTimeline
from src.observer.observation_correlator import ObservationCorrelator
from src.observer.action_episode_manager import ActionEpisodeManager
from src.vision.window_capture import find_acr_table_window, capture_window_crop

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))

HERO_READER = ROOT / "src/api/hero_cards_api_reader.py"

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
COORD_STATE = ROOT / "runtime/live/api_event_coordinator_state.json"
OBS_LOG = ROOT / "runtime/live/local_observations.jsonl"
TIMELINE_JSON = ROOT / "runtime/live/current_observation_timeline.json"
CORRELATOR_JSON = ROOT / "runtime/live/current_observation_correlator.json"
EPISODES_JSON = ROOT / "runtime/live/current_action_episodes.json"
BOARD_REQUESTS = ROOT / "runtime/live/board_requests.jsonl"
BOARD_RESULTS = ROOT / "runtime/live/board_results.jsonl"
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
        "hand_token": None,
        "board_request_id": None,
        "board_request_expected_len": None,
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

    kind = event.get("type")
    if kind == "hero_cards":
        print(f"[HAND] Hero cards: {' '.join(event.get('hero_cards') or [])}")
    elif kind == "table_snapshot":
        print(f"[HAND] Table snapshot: players={len(event.get('players') or [])} dealer={event.get('dealer_button_seat') or 'unknown'} hero_position={event.get('hero_position') or 'unknown'}")
    elif kind == "hero_decision":
        print("[ACTION] Hero to act")
    elif kind == "hero_action_complete":
        print("[ACTION] Hero action complete")
    elif kind == "board":
        board = event.get("board") or []
        street = {3: "FLOP", 4: "TURN", 5: "RIVER"}.get(len(board), "BOARD")
        print(f"[BOARD] {street}: {' '.join(board)}")
    elif kind == "hand_complete":
        print(f"[HAND] Complete: {event.get('result')}")
    else:
        print("[EVENT]", event)


def log_observation(changes):
    payload = changes.to_dict()
    payload["ts"] = time.time()
    OBS_LOG.open("a").write(json.dumps(payload) + "\n")
    # Detailed local observations are written to local_observations.jsonl.
    # Keep terminal output focused on hand/action/board events.


_CACHED_WINDOW = None


def capture():
    global _CACHED_WINDOW

    if _CACHED_WINDOW is None:
        _CACHED_WINDOW = find_acr_table_window()
        if _CACHED_WINDOW is None:
            return latest_capture()

    try:
        return capture_window_crop(_CACHED_WINDOW)
    except Exception:
        _CACHED_WINDOW = find_acr_table_window()
        if _CACHED_WINDOW is None:
            return latest_capture()
        return capture_window_crop(_CACHED_WINDOW)


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
        samples=4,
        delay=0.10,
        threshold=5.0,
    )
    return blink


def maybe_emit_hero_decision(state, visible, hero_visible):
    if state.get("phase") == "WAITING":
        state["hero_decision_active"] = False
        return state

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
        state["hand_token"] = uuid.uuid4().hex
        state["board_request_id"] = None
        state["board_request_expected_len"] = None
        emit({"type": "hero_cards", "hero_cards": cards})


    return state


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
        f.flush()


def queue_board_request(state, expected_len, frame):
    request_id = uuid.uuid4().hex

    append_jsonl(BOARD_REQUESTS, {
        "type": "board_request",
        "request_id": request_id,
        "hand_token": state.get("hand_token"),
        "expected_len": expected_len,
        "frame": str(frame),
        "ts": time.time(),
    })

    state["board_request_id"] = request_id
    state["board_request_expected_len"] = expected_len

    print(
        f"[BOARD] queued request={request_id[:8]} "
        f"expected={expected_len}"
    )

    return state


def find_board_result(request_id):
    if not request_id or not BOARD_RESULTS.exists():
        return None

    try:
        lines = BOARD_RESULTS.read_text().splitlines()
    except Exception:
        return None

    for line in reversed(lines):
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue

        if result.get("request_id") == request_id:
            return result

    return None


def apply_board_result(state, result):
    request_id = state.get("board_request_id")
    expected_len = state.get("board_request_expected_len")

    if result.get("request_id") != request_id:
        return state, False

    # Clear the pending request regardless of success so failure can retry.
    state["board_request_id"] = None
    state["board_request_expected_len"] = None

    if result.get("hand_token") != state.get("hand_token"):
        print("[BOARD] ignored stale result from another hand")
        return state, False

    if not result.get("ok"):
        print(
            f"[BOARD] worker result failed "
            f"error={result.get('error') or 'unknown'}"
        )
        return state, False

    board = result.get("board") or []

    if expected_len not in (3, 4, 5):
        print(f"[BOARD] invalid expected_len={expected_len}; ignoring")
        return state, False

    confirmed = state.get("confirmed_board_len", 0)
    required_next = 3 if confirmed == 0 else confirmed + 1

    if expected_len != required_next:
        print(
            f"[BOARD] stale sequence result expected={expected_len} "
            f"required={required_next}; ignoring"
        )
        return state, False

    if len(board) < expected_len:
        print(
            f"[BOARD] short worker result len={len(board)} "
            f"expected={expected_len}"
        )
        return state, False

    board_to_emit = board[:expected_len]
    state["confirmed_board_len"] = expected_len

    if state.get("hero_decision_active"):
        emit({"type": "hero_action_complete"})
        state["hero_decision_active"] = False

    if expected_len == 3:
        state["phase"] = "FLOP"
    elif expected_len == 4:
        state["phase"] = "TURN"
    elif expected_len == 5:
        state["phase"] = "RIVER"

    emit({"type": "board", "board": board_to_emit})
    return state, True


def maybe_read_board(state, count, frame):
    if state.get("phase") == "WAITING":
        return state

    pending_id = state.get("board_request_id")

    if pending_id:
        result = find_board_result(pending_id)

        if result is None:
            return state

        state, _ = apply_board_result(state, result)
        return state

    confirmed = state.get("confirmed_board_len", 0)

    if count not in (3, 4, 5):
        return state

    if count <= confirmed:
        return state

    expected_next = 3 if confirmed == 0 else confirmed + 1

    if expected_next not in (3, 4, 5):
        return state

    now = time.time()
    last_attempt = state.get("last_api_attempt_ts", 0)

    if now - last_attempt < 1.25:
        return state

    state["last_api_attempt_ts"] = now
    return queue_board_request(state, expected_next, frame)


def maybe_complete_early(state, count, hero_visible):
    phase = state.get("phase")

    if phase == "WAITING":
        state["hero_clear_seen"] = 0
        return state

    # If hero cards disappear, hero is out of the hand or the hand has ended.
    if not hero_visible:
        state["hero_clear_seen"] = state.get("hero_clear_seen", 0) + 1
    else:
        state["hero_clear_seen"] = 0

    if state["hero_clear_seen"] >= 4:
        emit({"type": "hand_complete", "result": "Hero cards cleared / hero folded or hand ended"})
        return fresh_state()

    # If board clears after any street, the hand ended before showdown/river completion.
    if phase in ("FLOP", "TURN") and count == 0:
        state["board_clear_seen"] = state.get("board_clear_seen", 0) + 1
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
    local_detector = LocalEventDetector()
    observer = ContinuousObserver()
    timeline = ObservationTimeline()
    correlator = ObservationCorrelator()
    episode_manager = ActionEpisodeManager()

    while True:
        frame = capture()

        img = cv2.imread(str(frame)) if frame else None
        if img is None:
            time.sleep(0.5)
            continue

        img = cv2.resize(img, (934, 696))
        changes = local_detector.detect(img)
        log_observation(changes)

        observations = observer.ingest_changes(
            changes,
            street=state.get("phase", "WAITING")
        )
        timeline.add_many(observations)
        timeline.write_json(TIMELINE_JSON)
        correlator.ingest(observations)
        CORRELATOR_JSON.write_text(json.dumps(correlator.summary(), indent=2))

        if state.get("phase") != "WAITING":
            episode_manager.ingest(observations)
            EPISODES_JSON.write_text(json.dumps(episode_manager.summary(), indent=2))

        hero_visible = changes.hero_cards_visible
        count = changes.board_count
        buttons_visible = changes.action_buttons_visible

        state = maybe_read_hero(state, hero_visible, count, frame)

        before_board_len = state.get("confirmed_board_len", 0)
        state = maybe_read_board(state, count, frame)
        board_emitted_this_cycle = state.get("confirmed_board_len", 0) != before_board_len

        # Do not mix a street transition and a Hero turn event in the same observation cycle.
        # Let the state machine consume the board event first, then evaluate Hero turn on the next frame.
        if board_emitted_this_cycle:
            save_state(state)
            time.sleep(0.5)
            continue

        # Blink sampling performs repeated captures and must stay off the hot path.
        blink_visible = False
        hero_turn_visible = buttons_visible

        if state.get("phase") != "WAITING":
            print(
                f"[HERO_CHECK] phase={state.get('phase')} "
                f"hero_visible={hero_visible} buttons={buttons_visible} "
                f"blink={blink_visible} active={state.get('hero_decision_active')}"
            )

        state = maybe_emit_hero_decision(state, hero_turn_visible, hero_visible)
        state = maybe_complete_early(state, count, hero_visible)
        state = maybe_complete_hand(state, count)

        save_state(state)

        if state.get("phase") == "WAITING":
            time.sleep(0.5)
        elif state.get("hero_decision_active"):
            time.sleep(0.05)
        else:
            time.sleep(0.10)


if __name__ == "__main__":
    main()
