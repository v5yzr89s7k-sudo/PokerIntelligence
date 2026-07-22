from pathlib import Path
import re
import json
import time
import subprocess
import cv2
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.events.detectors.action_buttons_detector import action_buttons_visible
from src.events.detectors.hero_turn_detector import HeroBlinkBuffer
from src.events.local_event_detector import LocalEventDetector
from src.events.participant_evidence_collector import (
    ParticipantEvidenceCollector,
)
from src.observer.continuous_observer import ContinuousObserver
from src.observer.observation_timeline import ObservationTimeline
from src.observer.observation_correlator import ObservationCorrelator
from src.observer.action_episode_manager import (
    ActionEpisodeManager,
    LATE_STACK_ATTACH_SECONDS,
)
from src.api.perception_latency import log as log_latency
from src.observer.action_inference_engine import ActionInferenceEngine
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)
from src.vision.window_capture import find_acr_table_window, capture_window_crop
from src.api.canonical_frame import to_canonical_frame
from src.vision.action_sequence_recorder import ActionSequenceRecorder
from src.vision.stack_reader import read_stack
from src.vision.dealer_detector import detect_dealer_button
from src.api.position_engine import assign_positions
from src.api.stack_transition_validator import (
    ACCEPT as STACK_ACCEPT,
    REJECT as STACK_REJECT,
    validate_stack_transition,
)

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))
PARTICIPANT_COLLECTOR = ParticipantEvidenceCollector()


def collect_participant_evidence(
    frame,
    frame_path,
    state,
):
    """
    Publish per-frame hand-start card-back evidence while Hero cards are
    visible and before the participant roster has been frozen.
    """
    hand_token = str(
        (state or {}).get("hand_token") or ""
    )

    if not hand_token:
        return None

    if frame is None or frame.size == 0:
        return None

    canonical = to_canonical_frame(
        frame,
        GEOM,
    )

    return PARTICIPANT_COLLECTOR.observe(
        canonical,
        GEOM,
        hand_token=hand_token,
        frame_path=str(frame_path or ""),
        started_ts=(
            (state or {}).get("hand_started_at")
            or (state or {}).get("hero_request_ts")
            or time.time()
        ),
    )


EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
COORD_STATE = ROOT / "runtime/live/api_event_coordinator_state.json"
STATE_MACHINE_STATE = (
    ROOT / "runtime/live/api_event_state_machine_state.json"
)

TABLE_CONTEXT_CACHE = ROOT / "runtime/live/table_context.json"
CANONICAL_HAND_JSON = ROOT / "runtime/live/canonical_hand.json"
OBS_LOG = ROOT / "runtime/live/local_observations.jsonl"
TIMELINE_JSON = ROOT / "runtime/live/current_observation_timeline.json"
CORRELATOR_JSON = ROOT / "runtime/live/current_observation_correlator.json"
EPISODES_JSON = ROOT / "runtime/live/current_action_episodes.json"
INFERRED_ACTIONS_JSON = ROOT / "runtime/live/current_inferred_actions.json"
BOARD_REQUESTS = ROOT / "runtime/live/board_requests.jsonl"
BOARD_RESULTS = ROOT / "runtime/live/board_results.jsonl"
HERO_REQUESTS = ROOT / "runtime/live/hero_requests.jsonl"
HERO_RESULTS = ROOT / "runtime/live/hero_results.jsonl"
POT_REQUESTS = ROOT / "runtime/live/pot_requests.jsonl"
POT_RESULTS = ROOT / "runtime/live/pot_results.jsonl"
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
        "last_hero_action_complete_phase": None,
        "hand_token": None,
        "board_request_id": None,
        "board_request_expected_len": None,
        "hero_request_id": None,
        "hero_request_token": None,
        "hero_request_ts": None,
        "pot_request_id": None,
        "pot_request_ts": None,
        "initial_pot_queued": False,
        "last_local_board_count": 0,
        "last_local_hero_visible": False,
        "pending_stack_reads": {},
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


def _crop_geometry_region(img, region):
    x = int(region["x"])
    y = int(region["y"])
    width = int(region["width"])
    height = int(region["height"])
    return img[y:y + height, x:x + width]


def _canonical_stack_values():
    """
    Read authoritative live stack values from CanonicalHand.

    The coordinator is read-only. The API event state machine remains the
    sole writer of canonical hand state.
    """
    if not CANONICAL_HAND_JSON.exists():
        return {}

    try:
        data = json.loads(CANONICAL_HAND_JSON.read_text())
    except Exception:
        return {}

    players = data.get("players") or {}
    values = {}

    if isinstance(players, list):
        players = {
            item.get("seat"): item
            for item in players
            if item.get("seat")
        }

    for seat, player in players.items():
        value = player.get("last_confirmed_stack_bb")

        if value is None:
            value = player.get("current_stack_bb")

        if value is None:
            value = player.get("starting_stack_bb")

        if value is None:
            continue

        try:
            values[seat] = float(value)
        except (TypeError, ValueError):
            continue

    return values


def enrich_stack_change_measurements(
    changes,
    img,
    state,
    *,
    prior_occupied_bet_regions=None,
    prior_commitment_seats=None,
):
    """
    Convert noisy stack-region movement into one settled quantitative
    transition.

    Raw stack changes are held until the region has remained quiet for
    STACK_SETTLE_SECONDS. Only then is that seat OCR-read and published as
    a STACK_CHANGED observation.
    """
    now = time.time()
    settle_seconds = 0.45
    minimum_delta_bb = 0.05

    prior_occupied_bet_regions = set(
        prior_occupied_bet_regions or []
    )
    prior_commitment_seats = set(
        prior_commitment_seats or []
    )

    # Quantitative stack transitions must be supported by at least two
    # agreeing OCR variants. Single-variant reads are too unstable to
    # mutate the live stack baseline.
    minimum_confidence = 0.95
    minimum_votes = 2

    # A single ambiguous OCR frame must not permanently discard a real
    # stack transition. Retry briefly while the stack display stabilizes.
    maximum_ocr_attempts = 5
    maximum_pending_seconds = 2.5

    raw_changed_seats = list(
        getattr(changes, "stack_changed_seats", [])
        or []
    )
    raw_details = dict(
        getattr(changes, "stack_change_details", {})
        or {}
    )

    pending = state.setdefault(
        "pending_stack_reads",
        {},
    )

    # CanonicalHand owns the authoritative stack baseline. The coordinator
    # reads it but never maintains a second persistent stack history.
    canonical_values = _canonical_stack_values()

    # Record movement, but do not publish it yet.
    for seat in raw_changed_seats:
        entry = pending.setdefault(
            seat,
            {
                "first_change_ts": now,
                "last_change_ts": now,
                "max_mean_diff": 0.0,
                "origin_street": state.get("phase", "WAITING"),
            },
        )

        entry["last_change_ts"] = now

        # If the stack transition began before Hero cards completed,
        # promote the transition to the current street as soon as the
        # hand becomes active.
        if (
            entry.get("origin_street") == "WAITING"
            and state.get("phase") != "WAITING"
        ):
            entry["origin_street"] = state.get("phase")

        mean_diff = float(
            (raw_details.get(seat) or {}).get("mean_diff")
            or 0.0
        )
        entry["max_mean_diff"] = max(
            float(entry.get("max_mean_diff") or 0.0),
            mean_diff,
        )

    settled_details = {}
    settled_seats = []

    for seat, entry in list(pending.items()):
        if now - float(entry["last_change_ts"]) < settle_seconds:
            continue

        # A quantitative transition requires a trusted prior value from
        # the canonical hand state.
        previous = canonical_values.get(seat)
        if previous is None:
            # The asynchronous table snapshot may still be initializing the
            # canonical hand. Preserve this pending transition and retry on a
            # later frame instead of permanently discarding it.
            wait_attempts = int(
                entry.get("baseline_wait_attempts")
                or 0
            ) + 1
            entry["baseline_wait_attempts"] = wait_attempts

            # Avoid flooding the terminal while the snapshot worker runs.
            if wait_attempts == 1 or wait_attempts % 10 == 0:
                print(
                    f"[STACK_SETTLE_WAIT] seat={seat} "
                    f"reason=canonical_baseline_not_ready "
                    f"attempt={wait_attempts}",
                    flush=True,
                )

            continue

        region = (
            GEOM.get("stack_regions", {})
            .get(seat)
        )

        if not region:
            pending.pop(seat, None)
            continue

        crop = _crop_geometry_region(img, region)
        if crop.size == 0:
            pending.pop(seat, None)
            continue

        reading = read_stack(crop)

        # Resolve large OCR disagreements against the last trusted stack.
        #
        # Continuity may promote an ambiguous OCR candidate only when the
        # transition is plausible. Otherwise preserve the resolver's original
        # low-confidence result so the settlement retry mechanism rejects it.
        raw_readings = reading.get("raw") or []
        candidate_values = [
            float(item["stack_bb"])
            for item in raw_readings
            if item.get("stack_bb") is not None
            and float(item["stack_bb"]) > 0.0
        ]

        if (
            previous is not None
            and int(reading.get("votes") or 0) < 2
            and len(set(candidate_values)) >= 2
            and (
                max(candidate_values) - min(candidate_values)
            ) > 20.0
        ):
            previous_value = float(previous)

            candidate_counts = {}
            for value in candidate_values:
                candidate_counts[value] = (
                    candidate_counts.get(value, 0) + 1
                )

            continuity_value = min(
                candidate_counts,
                key=lambda value: abs(previous_value - value),
            )
            continuity_votes = candidate_counts[
                continuity_value
            ]
            continuity_distance = abs(
                previous_value - continuity_value
            )

            # Stack increases are never wagers. A single OCR variant may only
            # be promoted when it is extremely close to the canonical value.
            # A two-variant candidate gets a wider—but still bounded—window.
            is_increase = (
                continuity_value > previous_value + 0.05
            )
            single_vote_plausible = (
                continuity_votes == 1
                and continuity_distance <= 3.0
            )
            consensus_plausible = (
                continuity_votes >= 2
                and continuity_distance
                <= max(12.0, previous_value * 0.35)
            )

            plausible = bool(
                not is_increase
                and (
                    single_vote_plausible
                    or consensus_plausible
                )
            )

            original_value = reading.get("stack_bb")

            if plausible:
                reading["stack_bb"] = continuity_value
                reading["stack_text"] = (
                    f"{continuity_value:g} BB"
                )
                reading["confidence"] = 0.95
                reading["votes"] = 2
                reading["mode"] = "continuity"

                print(
                    f"[STACK_CONTINUITY] seat={seat} "
                    f"previous={previous_value:.2f} "
                    f"resolver={original_value} "
                    f"selected={continuity_value:.2f} "
                    f"distance={continuity_distance:.2f} "
                    f"candidate_votes={continuity_votes} "
                    f"candidates={candidate_values}",
                    flush=True,
                )
            else:
                print(
                    f"[STACK_CONTINUITY_REJECT] seat={seat} "
                    f"previous={previous_value:.2f} "
                    f"resolver={original_value} "
                    f"nearest={continuity_value:.2f} "
                    f"distance={continuity_distance:.2f} "
                    f"candidate_votes={continuity_votes} "
                    f"candidates={candidate_values}",
                    flush=True,
                )

        current = reading.get("stack_bb")
        confidence = float(
            reading.get("confidence")
            or 0.0
        )
        votes = int(reading.get("votes") or 0)

        if (
            current is None
            or confidence < minimum_confidence
            or votes < minimum_votes
        ):
            attempts = int(entry.get("ocr_attempts") or 0) + 1
            entry["ocr_attempts"] = attempts

            pending_age = (
                now - float(entry.get("first_change_ts") or now)
            )

            retrying = (
                attempts < maximum_ocr_attempts
                and pending_age < maximum_pending_seconds
            )

            if not retrying:
                pending.pop(seat, None)

            print(
                f"[STACK_SETTLE_SKIP] seat={seat} "
                f"reason=untrusted_read "
                f"confidence={confidence:.2f} "
                f"votes={votes} "
                f"attempt={attempts} "
                f"retrying={retrying}",
                flush=True,
            )
            continue

        previous = float(previous)
        current = float(current)

        has_commitment_evidence = bool(
            seat in prior_occupied_bet_regions
            or seat in prior_commitment_seats
        )

        validation = validate_stack_transition(
            previous,
            current,
            confidence=confidence,
            votes=votes,
            phase=state.get("phase", "WAITING"),
            has_commitment_evidence=has_commitment_evidence,
            # No independent all-in detector exists yet.
            all_in_confirmed=False,
            minimum_confidence=minimum_confidence,
            minimum_votes=minimum_votes,
        )

        if validation.decision != STACK_ACCEPT:
            attempts = int(entry.get("validation_attempts") or 0) + 1
            entry["validation_attempts"] = attempts

            pending_age = (
                now - float(entry.get("first_change_ts") or now)
            )

            retrying = bool(
                validation.decision != STACK_REJECT
                and attempts < maximum_ocr_attempts
                and pending_age < maximum_pending_seconds
            )

            if not retrying:
                pending.pop(seat, None)

            print(
                f"[STACK_VALIDATE] seat={seat} "
                f"decision={validation.decision} "
                f"reason={validation.reason} "
                f"previous={previous:.2f} "
                f"current={current:.2f} "
                f"delta={validation.delta_bb:.2f} "
                f"commitment_evidence={has_commitment_evidence} "
                f"attempt={attempts} "
                f"retrying={retrying}",
                flush=True,
            )
            continue

        delta = validation.delta_bb

        # Zero deltas are visual noise. Negative deltas represent chips
        # returning to the stack or an OCR disagreement, not a wager.
        if delta < minimum_delta_bb:
            pending.pop(seat, None)

            print(
                f"[STACK_SETTLE_SKIP] seat={seat} "
                f"previous={previous:.2f} current={current:.2f} "
                f"delta={delta:.2f} reason=non_commitment",
                flush=True,
            )
            continue

        measurement = {
            "origin_street": entry.get(
                "origin_street",
                state.get("phase", "WAITING"),
            ),
            "mean_diff": float(
                entry.get("max_mean_diff")
                or 0.0
            ),
            "changed": True,
            "settled_ms": round(
                (now - float(entry["last_change_ts"])) * 1000.0,
                1,
            ),
            "stack_read_confidence": confidence,
            "stack_read_mode": reading.get(
                "mode",
                "unknown",
            ),
            "stack_text": reading.get(
                "stack_text",
                "",
            ),
            "previous_stack_bb": round(previous, 2),
            "current_stack_bb": round(current, 2),
            "delta_bb": delta,
        }

        settled_details[seat] = measurement
        settled_seats.append(seat)
        pending.pop(seat, None)

        emit({
            "type": "stack_update",
            "seat": seat,
            "previous_stack_bb": round(previous, 2),
            "current_stack_bb": round(current, 2),
            "delta_bb": delta,
            "confidence": confidence,
            "origin_street": measurement.get("origin_street"),
            "stack_read_mode": measurement.get("stack_read_mode"),
            "stack_text": measurement.get("stack_text"),
        })

        print(
            f"[STACK_TRANSITION] seat={seat} "
            f"previous={previous:.2f} "
            f"current={current:.2f} "
            f"delta={delta:.2f} "
            f"confidence={confidence:.2f}",
            flush=True,
        )

    # Suppress noisy instantaneous detector events. Downstream receives
    # only settled, quantitative stack transitions.
    changes.stack_changed_seats = settled_seats
    changes.stack_change_details = settled_details


def load_table_context():
    context = {
        "phase": "WAITING",
        "hero_position": "unknown",
        "dealer_button_seat": "",
        "positions": {},
        "players": [],
        "hand_started_at": None,
    }

    if TABLE_CONTEXT_CACHE.exists():
        try:
            cached = json.loads(
                TABLE_CONTEXT_CACHE.read_text()
            )

            context["hero_position"] = (
                cached.get("hero_position")
                or context["hero_position"]
            )
            context["dealer_button_seat"] = (
                cached.get("dealer_button_seat")
                or context["dealer_button_seat"]
            )
            context["positions"] = dict(
                cached.get("positions") or {}
            )
        except Exception:
            pass

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

    if event.get("type") == "table_context":
        TABLE_CONTEXT_CACHE.write_text(
            json.dumps(event, indent=2)
        )

    kind = event.get("type")
    if kind == "hero_cards":
        print(f"[HAND] Hero cards: {' '.join(event.get('hero_cards') or [])}")
    elif kind == "table_snapshot":
        print(f"[HAND] Table snapshot: players={len(event.get('players') or [])} dealer={event.get('dealer_button_seat') or 'unknown'} hero_position={event.get('hero_position') or 'unknown'}")
    elif kind == "table_context":
        print(
            f"[CONTEXT] hero_position={event.get('hero_position','unknown')} "
            f"dealer={event.get('dealer_button_seat') or 'unknown'} "
            f"seats={len(event.get('dealt_in_seats') or [])}"
        )
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


def parse_tournament_level(title):
    """
    Parse ACR tournament level metadata from a table-window title.

    Example:
        "... - 700 / 1,400, Ante 175 Hold'em ..."

    All canonical amounts are normalized to big blinds.
    """
    title = str(title or "")

    match = re.search(
        r"(\d[\d,]*)\s*/\s*(\d[\d,]*)"
        r"(?:\s*,?\s*Ante\s+(\d[\d,]*))?",
        title,
        flags=re.IGNORECASE,
    )

    if not match:
        return {}

    small_blind_chips = int(match.group(1).replace(",", ""))
    big_blind_chips = int(match.group(2).replace(",", ""))
    ante_chips = int((match.group(3) or "0").replace(",", ""))

    if big_blind_chips <= 0:
        return {}

    return {
        "small_blind_chips": small_blind_chips,
        "big_blind_chips": big_blind_chips,
        "ante_chips": ante_chips,
        "small_blind_bb": round(
            small_blind_chips / big_blind_chips,
            6,
        ),
        "big_blind_bb": 1.0,
        "ante_bb": round(
            ante_chips / big_blind_chips,
            6,
        ),
        "source": "window_title",
        "window_title": title,
    }


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


def maybe_emit_hero_decision(state, visible, hero_visible):
    if state.get("phase") == "WAITING":
        state["hero_decision_active"] = False
        return state

    if visible and hero_visible and not state.get("hero_decision_active"):
        emit({"type": "hero_decision"})
        state["hero_decision_active"] = True
        state["last_hero_action_complete_phase"] = None
        return state

    if not visible and state.get("hero_decision_active"):
        emit({"type": "hero_action_complete"})
        state["hero_decision_active"] = False
        state["last_hero_action_complete_phase"] = state.get("phase")
        return state

    if not visible:
        state["hero_decision_active"] = False

    return state


def queue_hero_request(state, frame):
    request_id = uuid.uuid4().hex
    queued_ts = time.time()

    # Prefer the provisional token created on first local Hero-card
    # visibility. Only create/reset here as a fallback when local hand-start
    # detection did not fire.
    hand_token = str(
        state.get("hand_token") or uuid.uuid4().hex
    )

    if PARTICIPANT_COLLECTOR.hand_token != hand_token:
        PARTICIPANT_COLLECTOR.reset(
            hand_token=hand_token,
            started_ts=(
                state.get("hand_started_at")
                or queued_ts
            ),
        )

    state["hand_token"] = hand_token
    state.setdefault(
        "hand_started_at",
        queued_ts,
    )

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

        level = parse_tournament_level(
            _CACHED_WINDOW.title
            if _CACHED_WINDOW is not None
            else ""
        )

        if level:
            print(
                "[LEVEL] "
                f"SB={level['small_blind_chips']} "
                f"BB={level['big_blind_chips']} "
                f"ante={level['ante_chips']} "
                f"ante_bb={level['ante_bb']}",
                flush=True,
            )
        else:
            print(
                "[LEVEL] unavailable from window title",
                flush=True,
            )

        frozen_participants = PARTICIPANT_COLLECTOR.freeze(
            hand_token=request_token,
            frozen_ts=time.time(),
        )

        print(
            f"[PARTICIPANT_FREEZE_PUBLISH] "
            f"count={len(frozen_participants)} "
            f"seats={frozen_participants}",
            flush=True,
        )

        dealer = detect_dealer_button(
            result["canonical_frame"]
        )

        position_players = [
            {"seat": seat}
            for seat in frozen_participants
        ]

        positions = assign_positions(
            position_players,
            dealer["dealer_button_seat"],
        )

        # Seed the fast table context with local stack OCR from the same
        # canonical Hero-card frame. GPT remains deferred name enrichment.
        local_players = []
        canonical_frame_path = result.get("canonical_frame")
        canonical_image = (
            cv2.imread(str(canonical_frame_path))
            if canonical_frame_path
            else None
        )

        if canonical_image is not None:
            canonical_image = cv2.resize(
                canonical_image,
                (934, 696),
            )

        for seat in frozen_participants:
            stack_result = {
                "stack_bb": None,
                "stack_text": "",
                "confidence": 0.0,
                "mode": "unavailable",
            }

            region = (GEOM.get("stack_regions") or {}).get(seat)

            if canonical_image is not None and region:
                stack_crop = _crop_geometry_region(
                    canonical_image,
                    region,
                )

                if stack_crop is not None and stack_crop.size:
                    try:
                        stack_result = read_stack(stack_crop)
                    except Exception as exc:
                        print(
                            f"[LOCAL_STACK] seat={seat} "
                            f"failed={type(exc).__name__}: {exc}",
                            flush=True,
                        )

            stack_bb = stack_result.get("stack_bb")
            confidence = float(
                stack_result.get("confidence") or 0.0
            )
            votes = int(
                stack_result.get("votes") or 0
            )

            trusted = (
                stack_bb is not None
                and float(stack_bb) > 0.0
                and confidence >= 0.95
                and votes >= 2
            )

            local_players.append({
                "seat": seat,
                "name": "",
                "stack_bb": (
                    float(stack_bb)
                    if trusted
                    else None
                ),
                "stack_text": (
                    str(stack_result.get("stack_text") or "")
                    if trusted
                    else ""
                ),
                "stack_confidence": confidence,
                "stack_read_mode": stack_result.get(
                    "mode",
                    "unknown",
                ),
                "is_hero": seat == "hero",
                "is_active": True,
            })

            print(
                f"[LOCAL_STACK] seat={seat} "
                f"stack={stack_bb if trusted else None} "
                f"confidence={confidence:.2f} "
                f"votes={votes} "
                f"trusted={trusted}",
                flush=True,
            )

        participant_evidence = (
            PARTICIPANT_COLLECTOR.snapshot()
        )

        emit({
            "type": "table_context",
            "hand_token": request_token,
            "participant_frame_count": int(
                participant_evidence.get("frame_count")
                or 0
            ),
            "dealer_button_seat": dealer["dealer_button_seat"],
            "dealt_in_seats": frozen_participants,
            "positions": positions,
            "hero_position": positions.get(
                "hero",
                "unknown",
            ),
            "players": local_players,
        })

        emit({
            "type": "hero_cards",
            "hero_cards": cards,
            "source_request_id": pending_id,
            "hand_token": request_token,
            "canonical_frame": result.get("canonical_frame"),
            "level": level,
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
        state["last_hero_action_complete_phase"] = state.get("phase")

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


def queue_pot_request(state, frame):
    if frame is None:
        return state

    request_id = uuid.uuid4().hex

    append_jsonl(POT_REQUESTS, {
        "type": "pot_request",
        "request_id": request_id,
        "hand_token": state.get("hand_token"),
        "frame": str(frame),
        "ts": time.time(),
    })

    state["pot_request_id"] = request_id
    state["pot_request_ts"] = time.time()

    log_latency(
        "queued",
        request_id=request_id,
        worker="pot",
        hand_token=state.get("hand_token"),
        frame=str(frame),
    )

    print(f"[POT] queued request={request_id[:8]}", flush=True)
    return state


def find_pot_result(request_id):
    if not request_id or not POT_RESULTS.exists():
        return None

    try:
        lines = POT_RESULTS.read_text().splitlines()
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


def apply_pot_result(state, result):
    request_id = state.get("pot_request_id")

    if result.get("request_id") != request_id:
        return state, False

    state["pot_request_id"] = None
    state["pot_request_ts"] = None

    result_token = result.get("hand_token")
    current_token = state.get("hand_token")

    if result_token and current_token and result_token != current_token:
        print("[POT] ignored stale result from another hand", flush=True)
        return state, False

    log_latency(
        "coordinator_consumed",
        request_id=request_id,
        worker="pot",
        ok=result.get("ok"),
        elapsed_ms=result.get("elapsed_ms"),
    )

    if not result.get("ok"):
        print(
            f"[POT] worker result failed "
            f"error={result.get('error') or 'unknown'} "
            f"raw={result.get('raw_text')!r}",
            flush=True,
        )
        return state, False

    pot_bb = result.get("pot_bb")

    try:
        pot_bb = float(pot_bb)
    except (TypeError, ValueError):
        print(f"[POT] invalid result pot={pot_bb!r}", flush=True)
        return state, False

    if not 0.1 <= pot_bb <= 1000.0:
        print(f"[POT] out-of-range result pot={pot_bb}", flush=True)
        return state, False

    emit({
        "type": "pot_update",
        "pot_bb": round(pot_bb, 2),
        "raw_text": result.get("raw_text"),
        "source_request_id": request_id,
        "confidence": result.get("confidence"),
    })

    print(
        f"[POT] observed={pot_bb:.2f} BB "
        f"raw={result.get('raw_text')!r}",
        flush=True,
    )

    return state, True


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
                # Queue the initial pot read immediately after the hand
                # becomes active so current_hand.txt has a starting pot
                # before the first betting round completes.
                if state.get("pot_request_id") is None:
                    latest = latest_capture()
                    if latest is not None:
                        state = queue_pot_request(state, latest)

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

    pot_request_id = state.get("pot_request_id")

    if pot_request_id:
        pot_result = find_pot_result(pot_request_id)

        if pot_result is not None:
            state, pot_emitted = apply_pot_result(
                state,
                pot_result,
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
        completed_phase = state.get("last_hero_action_complete_phase")

        if completed_phase == phase:
            emit({
                "type": "hero_fold",
                "street": phase,
            })
            result = f"Hero folded on {str(phase).lower()}"
        else:
            result = "Hero cards cleared / hand ended"

        emit({
            "type": "hand_complete",
            "result": result,
        })
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
    Require position context preflop and allow settled stack OCR evidence
    to attach before a voluntary chip episode is inferred permanently.
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

    context = item.get("table_context") or {}
    positions = context.get("positions") or {}
    seat = item.get("seat") or "unknown"

    position = positions.get(seat)

    if not position and seat == "hero":
        position = context.get("hero_position")

    position = str(position or "unknown").upper()

    if (
        street == "PREFLOP"
        and position == "UNKNOWN"
    ):
        return False

    evidence = set(
        item.get("observation_types")
        or []
    )

    # Forced blind posts are objective from position and do not require
    # a late quantitative stack read before inference.
    if (
        street == "PREFLOP"
        and position in {"SB", "BB"}
        and "bet_region_occupied" in evidence
    ):
        return True

    # Quantitative stack OCR may arrive after the visual episode closes.
    # Do not permanently process a voluntary bet-only episode until the
    # coordinator's 2.5-second stack retry window has elapsed.
    if (
        "bet_region_occupied" in evidence
        and "stack_changed" not in evidence
    ):
        ended_ts = item.get("ended_ts")

        if ended_ts is None:
            return False

        return (
            time.time() - float(ended_ts)
            >= LATE_STACK_ATTACH_SECONDS
        )

    return True


def main():
    print("api_event_coordinator running event-only mode. Ctrl+C to stop.")
    print(f"Events: {EVENT_LOG}")
    state = load_state()
    local_detector = LocalEventDetector()
    hero_blink_buffer = HeroBlinkBuffer(
        max_samples=6,
        diff_threshold=5.0,
        mean_range_threshold=5.0,
        required_transitions=2,
    )
    previous_blink_visible = False

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

        # Continuously accumulate hand-start participant evidence while
        # the coordinator is already processing live frames. This is
        # intentionally lightweight and independent of API latency.
        collect_participant_evidence(
            img,
            frame,
            state,
        )

        changes = local_detector.detect(img)

        # Hero cards appear at the deal, before any player can act.
        # Start participant evidence immediately instead of waiting for
        # Hero API request stability. This preserves early-position players
        # who may fold before the asynchronous Hero reader completes.
        local_hero_visible = bool(
            getattr(changes, "hero_cards_visible", False)
            or getattr(changes, "hero_visible", False)
        )

        if (
            state.get("phase") == "WAITING"
            and local_hero_visible
            and not state.get("hand_token")
        ):
            provisional_hand_token = uuid.uuid4().hex
            provisional_started_ts = time.time()

            state["hand_token"] = provisional_hand_token
            state["hand_started_at"] = provisional_started_ts

            PARTICIPANT_COLLECTOR.reset(
                hand_token=provisional_hand_token,
                started_ts=provisional_started_ts,
            )

            print(
                "[HAND_START_LOCAL] "
                f"token={provisional_hand_token[:8]} "
                "source=hero_cards_visible",
                flush=True,
            )

            # Include the same frame that triggered local hand start.
            collect_participant_evidence(
                img,
                frame,
                state,
            )

        current_stack_street = str(
            state.get("phase") or "WAITING"
        ).upper()

        prior_commitment_seats = (
            commitment_tracker.committed_players(
                current_stack_street
            )
            if current_stack_street != "WAITING"
            else []
        )

        enrich_stack_change_measurements(
            changes,
            img,
            state,
            prior_occupied_bet_regions=(
                previous_occupied_bet_regions
            ),
            prior_commitment_seats=prior_commitment_seats,
        )

        log_observation(changes)

        # Queue the first pot read as soon as the state machine has
        # initialized CanonicalHand from the authoritative table snapshot.
        # Do not wait for a later visual pot-change transition.
        state_machine_state = {}

        if STATE_MACHINE_STATE.exists():
            try:
                state_machine_state = json.loads(
                    STATE_MACHINE_STATE.read_text()
                )
            except Exception:
                state_machine_state = {}

        if (
            state.get("phase") != "WAITING"
            and state_machine_state.get("canonical_snapshot_ready")
            and not state.get("initial_pot_queued")
            and state.get("pot_request_id") is None
        ):
            state = queue_pot_request(state, frame)
            state["initial_pot_queued"] = True
            print("[POT] initial canonical request queued", flush=True)

        if (
            state.get("phase") != "WAITING"
            and bool(getattr(changes, "pot_changed", False))
            and state.get("pot_request_id") is None
        ):
            state = queue_pot_request(state, frame)

        sequence_recorder.record(
            frame=img,
            changes=changes,
            state=state,
            source_frame=frame,
        )

        print(
            "[CHANGES]",
            "stack_changed_seats=", getattr(changes, "stack_changed_seats", None),
            "bet_region_appeared=", getattr(changes, "bet_region_appeared", None),
            "bet_region_cleared=", getattr(changes, "bet_region_cleared", None),
            flush=True,
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
            # Temporary compatibility input until a real semantic betting
            # state model is implemented and validated.
            table_context["prior_occupied_bet_regions"] = sorted(
                previous_occupied_bet_regions
            )

            print(
                "[TABLE_CONTEXT]",
                "street=", current_commitment_street,
                "prior_commitments=",
                table_context.get(
                    "prior_voluntary_commitment_seats"
                ),
                "prior_occupied=",
                table_context.get(
                    "prior_occupied_bet_regions"
                ),
                flush=True,
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

        # Preserve this frame's confirmed bet occupancy as context for the
        # next perception frame.
        previous_occupied_bet_regions = set(
            changes.occupied_bet_regions
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

        # Non-blocking temporal Hero-turn sensor.
        # Reuses the coordinator's existing captured frame.
        blink_visible = False

        if hero_visible and frame:
            blink_frame = cv2.imread(str(frame))

            if blink_frame is not None:
                blink_frame = cv2.resize(blink_frame, (934, 696))
                blink_visible = hero_blink_buffer.update(
                    blink_frame,
                    GEOM,
                )
        else:
            hero_blink_buffer.reset()

        if blink_visible != previous_blink_visible:
            summary = hero_blink_buffer.summary()
            print(
                f"[HERO_BLINK] visible={blink_visible} "
                f"max_diff={summary['max_diff']:.3f} "
                f"mean_range={summary['mean_range']:.3f} "
                f"samples={summary['sample_count']}",
                flush=True,
            )
            previous_blink_visible = blink_visible

        hero_turn_visible = blink_visible or buttons_visible

        state = maybe_emit_hero_decision(
            state,
            hero_turn_visible,
            hero_visible,
        )
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
