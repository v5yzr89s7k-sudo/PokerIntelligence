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
from src.api.perception_latency import log as log_latency
from src.observer.action_inference_engine import ActionInferenceEngine
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)
from src.vision.window_capture import find_acr_table_window, capture_window_crop
from src.vision.action_sequence_recorder import ActionSequenceRecorder

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))


EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
COORD_STATE = ROOT / "runtime/live/api_event_coordinator_state.json"
STATE_MACHINE_STATE = (
    ROOT / "runtime/live/api_event_state_machine_state.json"
)
OBS_LOG = ROOT / "runtime/live/local_observations.jsonl"
TIMELINE_JSON = ROOT / "runtime/live/current_observation_timeline.json"
CORRELATOR_JSON = ROOT / "runtime/live/current_observation_correlator.json"
EPISODES_JSON = ROOT / "runtime/live/current_action_episodes.json"
INFERRED_ACTIONS_JSON = ROOT / "runtime/live/current_inferred_actions.json"
BOARD_REQUESTS = ROOT / "runtime/live/board_requests.jsonl"
BOARD_RESULTS = ROOT / "runtime/live/board_results.jsonl"
HERO_REQUESTS = ROOT / "runtime/live/hero_requests.jsonl"
HERO_RESULTS = ROOT / "runtime/live/hero_results.jsonl"
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
        "hero_request_id": None,
        "hero_request_token": None,
        "hero_request_ts": None,
        "last_local_board_count": 0,
        "last_local_hero_visible": False,
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


def load_table_context():
    context = {
        "phase": "WAITING",
        "hero_position": "unknown",
        "dealer_button_seat": "",
        "positions": {},
        "players": [],
        "hand_started_at": None,
    }

    if not STATE_MACHINE_STATE.exists():
        return context

    try:
        state = json.loads(
            STATE_MACHINE_STATE.read_text()
        )
    except Exception:
        return context

    context["phase"] = (
        state.get("phase")
        or "WAITING"
    )
    context["hero_position"] = (
        state.get("hero_position")
        or "unknown"
    )
    context["dealer_button_seat"] = (
        state.get("dealer_button_seat")
        or ""
    )
    context["positions"] = dict(
        state.get("positions")
        or {}
    )
    context["players"] = list(
        state.get("players")
        or []
    )
    context["hand_started_at"] = (
        state.get("hand_started_at")
    )

    return context


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


def queue_hero_request(state, frame):
    request_id = uuid.uuid4().hex
    hand_token = uuid.uuid4().hex

    queued_ts = time.time()

    append_jsonl(HERO_REQUESTS, {
        "type": "hero_request",
        "request_id": request_id,
        "hand_token": hand_token,
        "frame": str(frame),
        "ts": queued_ts,
    })

    log_latency(
        "queued",
        request_id=request_id,
        worker="hero",
        hand_token=hand_token,
        frame=str(frame),
    )

    state["hero_request_id"] = request_id
    state["hero_request_token"] = hand_token
    state["hero_request_ts"] = time.time()

    print(f"[HERO] queued request={request_id[:8]}")
    return state


def find_hero_result(request_id):
    if not request_id or not HERO_RESULTS.exists():
        return None

    try:
        lines = HERO_RESULTS.read_text().splitlines()
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


def maybe_read_hero(state, hero_visible, board_count, frame):
    if state.get("phase") != "WAITING":
        return state

    pending_id = state.get("hero_request_id")

    if pending_id:
        result = find_hero_result(pending_id)

        if result is None:
            request_ts = state.get("hero_request_ts") or time.time()
            pending_seconds = time.time() - request_ts

            # A queued request owns a captured frame. Temporary local
            # hero-visibility flicker must not cancel valid in-flight work.
            # Valid Hold'em board counts are 0, 3, 4, and 5.
            # Transient local counts of 1 or 2 are detector noise and must
            # not cancel a valid in-flight Hero-card request.
            if board_count in {3, 4, 5}:
                print(
                    f"[HERO] cancel pending request because "
                    f"valid board_count={board_count}"
                )
                state["hero_request_id"] = None
                state["hero_request_token"] = None
                state["hero_request_ts"] = None
                state["hero_visible_seen"] = 0

            elif pending_seconds >= 20.0:
                print(
                    f"[HERO] pending request timed out after "
                    f"{pending_seconds:.1f}s"
                )
                state["hero_request_id"] = None
                state["hero_request_token"] = None
                state["hero_request_ts"] = None
                state["hero_visible_seen"] = 0

            return state

        request_token = state.get("hero_request_token")
        request_ts = state.get("hero_request_ts")

        log_latency(
            "coordinator_consumed",
            request_id=pending_id,
            worker="hero",
            ok=result.get("ok"),
            elapsed_ms=result.get("elapsed_ms"),
        )

        state["hero_request_id"] = None
        state["hero_request_token"] = None
        state["hero_request_ts"] = None

        if result.get("hand_token") != request_token:
            print("[HERO] ignored stale worker result")
            return state

        if board_count != 0:
            print(
                "[HERO] ignored result because board has already advanced"
            )
            state["hero_visible_seen"] = 0
            return state

        if not result.get("ok"):
            print(
                f"[HERO] worker result failed "
                f"error={result.get('error') or 'unknown'}"
            )
            state["hero_visible_seen"] = 0
            return state

        cards = result.get("hero_cards") or []

        if len(cards) != 2 or not all(cards):
            print(f"[HERO] invalid worker cards={cards}")
            state["hero_visible_seen"] = 0
            return state

        if request_ts is not None:
            total_ms = (time.time() - request_ts) * 1000.0
            worker_ms = result.get("elapsed_ms")
            print(
                f"[LATENCY] HERO total={total_ms:.1f}ms "
                f"worker={worker_ms}ms"
            )

        state["hero_read"] = True
        state["phase"] = "PREFLOP"
        state["hero_clear_seen"] = 0
        state["hand_token"] = request_token
        state["board_request_id"] = None
        state["board_request_expected_len"] = None

        emit({
            "type": "hero_cards",
            "hero_cards": cards,
            "source_request_id": pending_id,
            "hand_token": request_token,
        })

        log_latency(
            "event_emitted",
            request_id=pending_id,
            worker="hero",
            event_type="hero_cards",
            hero_cards=cards,
        )

        return state

    if not hero_visible:
        state["hero_visible_seen"] = 0
        return state

    if board_count != 0:
        print(f"[HERO] visible but board_count={board_count}; waiting for clean hand")
        state["hero_visible_seen"] = 0
        return state

    state["hero_visible_seen"] = state.get("hero_visible_seen", 0) + 1

    if state["hero_visible_seen"] < 2:
        return state

    return queue_hero_request(state, frame)


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
        f.flush()


def queue_board_request(state, expected_len, frame):
    request_id = uuid.uuid4().hex

    queued_ts = time.time()

    append_jsonl(BOARD_REQUESTS, {
        "type": "board_request",
        "request_id": request_id,
        "hand_token": state.get("hand_token"),
        "expected_len": expected_len,
        "frame": str(frame),
        "ts": queued_ts,
    })

    log_latency(
        "queued",
        request_id=request_id,
        worker="board",
        hand_token=state.get("hand_token"),
        expected_len=expected_len,
        frame=str(frame),
    )

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

    log_latency(
        "event_emitted",
        request_id=request_id,
        worker="board",
        event_type="board",
        expected_len=expected_len,
        board=board_to_emit,
    )

    return state, True


def maybe_read_board(state, count, frame):
    if state.get("phase") == "WAITING":
        return state

    pending_id = state.get("board_request_id")

    if pending_id:
        result = find_board_result(pending_id)

        if result is None:
            return state

        log_latency(
            "coordinator_consumed",
            request_id=pending_id,
            worker="board",
            ok=result.get("ok"),
            elapsed_ms=result.get("elapsed_ms"),
            expected_len=result.get("expected_len"),
        )

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


def consume_ready_worker_results(state):
    """
    Consume completed worker results before performing another expensive
    capture/perception cycle.

    Returns:
        (state, consumed_result, emitted_board)
    """
    consumed = False
    board_emitted = False

    hero_request_id = state.get("hero_request_id")

    if hero_request_id:
        hero_result = find_hero_result(hero_request_id)

        if hero_result is not None:
            before_phase = state.get("phase")

            state = maybe_read_hero(
                state,
                bool(state.get("last_local_hero_visible")),
                int(state.get("last_local_board_count") or 0),
                None,
            )

            consumed = True

            if before_phase == "WAITING" and state.get("phase") != "WAITING":
                save_state(state)
                return state, True, False

    board_request_id = state.get("board_request_id")

    if board_request_id:
        board_result = find_board_result(board_request_id)

        if board_result is not None:
            log_latency(
                "coordinator_consumed",
                request_id=board_request_id,
                worker="board",
                ok=board_result.get("ok"),
                elapsed_ms=board_result.get("elapsed_ms"),
                expected_len=board_result.get("expected_len"),
                fast_path=True,
            )

            state, board_emitted = apply_board_result(
                state,
                board_result,
            )
            consumed = True

    if consumed:
        save_state(state)

    return state, consumed, board_emitted


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


def episode_ready_for_inference(episode):
    """
    Preflop action interpretation requires a position map. Postflop
    episodes may still be inferred without position context.
    """
    item = (
        episode.to_dict()
        if hasattr(episode, "to_dict")
        else episode
    )

    street = str(
        item.get("street")
        or "unknown"
    ).upper()

    if street != "PREFLOP":
        return True

    context = item.get("table_context") or {}
    positions = context.get("positions") or {}
    seat = item.get("seat") or "unknown"

    position = positions.get(seat)

    if not position and seat == "hero":
        position = context.get("hero_position")

    return bool(
        position
        and str(position).lower() != "unknown"
    )


def main():
    print("api_event_coordinator running event-only mode. Ctrl+C to stop.")
    print(f"Events: {EVENT_LOG}")
    state = load_state()
    local_detector = LocalEventDetector()
    sequence_recorder = ActionSequenceRecorder(
        max_frames=240
    )
    sequence_dir = sequence_recorder.start_session()
    print(
        f"[DEBUG_SEQUENCE] recording to {sequence_dir}",
        flush=True,
    )

    observer = ContinuousObserver()
    timeline = ObservationTimeline()
    correlator = ObservationCorrelator()
    episode_manager = ActionEpisodeManager()
    inference_engine = ActionInferenceEngine()
    commitment_tracker = StreetCommitmentTracker()
    commitment_street = "WAITING"
    last_deferred_count = None
    previous_occupied_bet_regions = set()

    INFERRED_ACTIONS_JSON.write_text(
        json.dumps(inference_engine.to_dict(), indent=2)
    )

    while True:
        state, consumed_result, board_emitted_fast = (
            consume_ready_worker_results(state)
        )

        if consumed_result:
            # Let downstream consumers observe emitted worker events before
            # performing another full screen-perception cycle.
            time.sleep(0.01 if not board_emitted_fast else 0.05)
            continue

        frame = capture()

        img = cv2.imread(str(frame)) if frame else None
        if img is None:
            time.sleep(0.5)
            continue

        img = cv2.resize(img, (934, 696))
        changes = local_detector.detect(img)
        log_observation(changes)

        sequence_recorder.record(
            frame=img,
            changes=changes,
            state=state,
            source_frame=frame,
        )

        observations = observer.ingest_changes(
            changes,
            street=state.get("phase", "WAITING")
        )
        timeline.add_many(observations)
        timeline.write_json(TIMELINE_JSON)
        correlator.ingest(observations)
        CORRELATOR_JSON.write_text(json.dumps(correlator.summary(), indent=2))

        if state.get("phase") != "WAITING":
            table_context = load_table_context()

            current_commitment_street = str(
                state.get("phase")
                or "WAITING"
            ).upper()

            if current_commitment_street != commitment_street:
                commitment_tracker.reset_street(
                    current_commitment_street
                )
                commitment_street = current_commitment_street

            table_context["prior_voluntary_commitment_seats"] = (
                commitment_tracker.committed_players(
                    current_commitment_street
                )
            )

            # Capture occupancy from the preceding perception frame.
            # This reveals whether a newly committing seat was already
            # facing chips from another player.
            table_context["prior_occupied_bet_regions"] = sorted(
                previous_occupied_bet_regions
            )

            episode_manager.set_table_context(
                table_context
            )
            episode_manager.ingest(observations)

            backfilled = episode_manager.backfill_table_context(
                table_context
            )

            if backfilled:
                print(
                    f"[CONTEXT] backfilled episodes={backfilled} "
                    f"hero_position={table_context.get('hero_position')} "
                    f"positions={len(table_context.get('positions') or {})}",
                    flush=True,
                )

            EPISODES_JSON.write_text(
                json.dumps(episode_manager.summary(), indent=2)
            )

            ready_closed = [
                episode
                for episode in episode_manager.closed
                if episode_ready_for_inference(episode)
            ]

            deferred_count = (
                len(episode_manager.closed)
                - len(ready_closed)
            )

            if deferred_count != last_deferred_count:
                if deferred_count:
                    print(
                        f"[INFERENCE] deferred preflop episodes="
                        f"{deferred_count} waiting_for_positions",
                        flush=True,
                    )
                elif last_deferred_count:
                    print(
                        "[INFERENCE] deferred preflop "
                        "episodes resolved",
                        flush=True,
                    )

                last_deferred_count = deferred_count

            new_actions = inference_engine.ingest_closed(
                ready_closed
            )

            if new_actions:
                for action in new_actions:
                    print(
                        f"[INFERRED] {action.street} {action.seat} "
                        f"{action.action} confidence={action.confidence:.2f}"
                    )

                    if (
                        action.action in {
                            "BET_OR_RAISE",
                            "CALL_OR_RAISE",
                            "CALL",
                        }
                        and action.confidence >= 0.70
                    ):
                        commitment_tracker.record_commitment(
                            action.street,
                            action.seat,
                        )

                    emit({
                        "type": "inferred_action",
                        **action.to_dict(),
                    })

                INFERRED_ACTIONS_JSON.write_text(
                    json.dumps(inference_engine.to_dict(), indent=2)
                )

        hero_visible = changes.hero_cards_visible
        count = changes.board_count
        buttons_visible = changes.action_buttons_visible

        state["last_local_hero_visible"] = bool(hero_visible)
        state["last_local_board_count"] = int(count or 0)

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

        # Poll worker result files aggressively only while requests are pending.
        # This removes avoidable coordinator delay without increasing API calls.
        if state.get("hero_request_id") is not None:
            time.sleep(0.02)
        elif state.get("board_request_id") is not None:
            time.sleep(0.02)
        elif state.get("phase") == "WAITING":
            time.sleep(0.5)
        elif state.get("hero_decision_active"):
            time.sleep(0.05)
        else:
            time.sleep(0.10)


if __name__ == "__main__":
    main()
