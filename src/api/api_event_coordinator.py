from pathlib import Path
import re
import json
import time
import os
import subprocess
import cv2
import sys
import uuid
from collections import deque
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.events.detectors.action_buttons_detector import action_buttons_visible
from src.events.detectors.hero_turn_detector import HeroBlinkBuffer
from src.events.detectors.seat_occupancy_detector import occupied_seats
from src.events.local_event_detector import ChangeSet, LocalEventDetector
from src.events.detectors.bet_region_detector import bet_region_occupancy
from src.events.participant_evidence_collector import (
    ParticipantEvidenceCollector,
)
from src.observer.continuous_observer import ContinuousObserver
from src.observer.observation_timeline import ObservationTimeline
from src.observer.observation_correlator import ObservationCorrelator
from src.observer.action_qualifier import ActionQualifier

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
    LATE_STACK_ATTACH_SECONDS,
)

from src.observer.street_episode_scheduler import (
    StreetEpisodeScheduler,
)
from src.api.perception_latency import log as log_latency
from src.observer.action_inference_engine import ActionInferenceEngine
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)
from src.state.recent_stack_observations import (
    RecentStackObservations,
)
from src.vision.window_capture import find_acr_table_window, capture_window_crop
from src.api.canonical_frame import to_canonical_frame
from src.api.paced_replay_capture import PacedReplayCapture
from src.capture.sck_frame_source import SCKFrameSource
from src.vision.action_sequence_recorder import ActionSequenceRecorder
from src.vision.winner_detector import detect_winner
from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)
from src.vision.stack_candidate_resolver import (
    resolve_stack_candidates,
)
from src.bootstrap.hero_bootstrap import (
    HeroBootstrap,
    bootstrap_local_stacks,
)
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
COORDINATOR_TIMING = ROOT / "runtime/live/coordinator_timing.jsonl"
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
ACTION_QUALIFICATIONS_JSON = (
    ROOT / "runtime/live/current_action_qualifications.json"
)
EPISODE_SCHEDULER_JSON = (
    ROOT / "runtime/live/pending_episode_scheduler.json"
)

BOARD_REQUESTS = ROOT / "runtime/live/board_requests.jsonl"
BOARD_RESULTS = ROOT / "runtime/live/board_results.jsonl"
HERO_REQUESTS = ROOT / "runtime/live/hero_requests.jsonl"
HERO_RESULTS = ROOT / "runtime/live/hero_results.jsonl"
POT_REQUESTS = ROOT / "runtime/live/pot_requests.jsonl"
POT_RESULTS = ROOT / "runtime/live/pot_results.jsonl"
BET_AMOUNT_REQUESTS = ROOT / "runtime/live/bet_amount_requests.jsonl"
BET_AMOUNT_RESULTS = ROOT / "runtime/live/bet_amount_results.jsonl"

STACK_REQUESTS = ROOT / "runtime/live/stack_requests.jsonl"
STACK_RESULTS = ROOT / "runtime/live/stack_results.jsonl"

# One semantic interval owns settled-stack timing everywhere:
# initial settlement, retry scheduling, and deterministic replay
# result visibility.
STACK_SETTLE_SECONDS = 0.45

# A missing board result may not monopolize board transport indefinitely.
# This coordinator ownership deadline is intentionally separate from the
# OpenAI client's lower-level network timeout.
BOARD_REQUEST_TIMEOUT_SECONDS = 5.0

BOUNDARY_STACK_REQUESTS = (
    ROOT / "runtime/live/boundary_stack_requests.jsonl"
)
BETTING_ROUND_STATUS = (
    ROOT / "runtime/live/betting_round_status.json"
)

EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)


def fresh_state():
    return {
        "phase": "WAITING",
        "hero_read": False,
        "confirmed_board_len": 0,
        "confirmed_board": [],
        # A longer board read may expose an earlier API card error.
        # Never rewrite confirmed board from one contradictory read.
        # Two identical independently requested longer reads are
        # required before repairing the shorter confirmed prefix.
        "board_prefix_contradiction": None,
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
        "board_request_ts": None,
        # Replay-only semantic ownership timestamp. Live requests leave this
        # unset and retain the existing asynchronous timeout behavior.
        "board_request_replay_frame_ts": None,
        "hero_request_id": None,
        "hero_request_token": None,
        "hero_request_ts": None,
        "pot_request_id": None,
        "pot_request_ts": None,
        "pot_request_purpose": None,
        "pot_request_forced_baseline_bb": None,
        "pending_bet_amount_requests": {},
        "deferred_bet_amount_results": {},
        "initial_bet_inventory_done": False,
        "last_valid_river_frame": None,
        "terminal_pot_pending": False,
        "terminal_pot_request_id": None,
        "terminal_pot_started_ts": None,
        # Hand ownership ends before terminal-pot bookkeeping necessarily
        # finishes. Once frozen, new table activity may not become old-hand
        # action evidence.
        "terminal_action_frozen": False,
        "terminal_freeze_reason": None,
        "winner_seat": None,
        "initial_pot_queued": False,
        "last_local_board_count": 0,
        "last_local_hero_visible": False,
        "pending_stack_reads": {},
        # Seat-local street ownership for an active physical bet-region
        # lifecycle. Wall-clock completion or later board visibility must not
        # relabel evidence that belongs to an already-started commitment.
        "bet_region_street_owners": {},
        "pending_stack_worker_requests": {},
        # Starting-stack OCR gets one immediate bootstrap attempt. Seats whose
        # value remains ambiguous are retried incrementally from subsequent
        # clean PREFLOP frames instead of waiting for a stack-motion event to
        # accidentally recover their baseline.
        "pending_startup_stack_seats": [],
        "startup_stack_retry_index": 0,
        "startup_stack_last_retry_ts": 0.0,
        "bootstrap_occupancy_diagnosed": False,
        "last_boundary_stack_request_key": None,
        # A physical street boundary may appear before the state machine has
        # consumed quantitative old-street events emitted on the same frame.
        # Preserve the boundary without freezing poker ownership prematurely.
        "pending_boundary_route": None,
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


def _canonical_player_ineligible_for_settled_stack(seat):
    """
    Return True only when authoritative CanonicalHand state positively
    establishes that this seat can no longer own a betting commitment.

    This is deliberately fail-open. Missing, unreadable, incomplete, or
    not-yet-published canonical state must preserve existing transport
    behavior rather than suppress legitimate quantitative evidence.
    """
    if not seat or not CANONICAL_HAND_JSON.exists():
        return False

    try:
        data = json.loads(CANONICAL_HAND_JSON.read_text())
    except Exception:
        return False

    players = data.get("players") or {}

    if isinstance(players, list):
        players = {
            item.get("seat"): item
            for item in players
            if isinstance(item, dict) and item.get("seat")
        }

    if not isinstance(players, dict):
        return False

    player = players.get(seat)

    if not isinstance(player, dict):
        return False

    return bool(
        player.get("folded") is True
        or player.get("active") is False
    )


def event_street_for_frame(state, local_board_count):
    """
    Resolve the street for local perception events on the current frame.

    Canonical state remains API-confirmed and authoritative for hand state.
    This resolver exists only for event-time attribution while asynchronous
    board confirmation is still pending.

    Only valid poker board lengths may advance the provisional street.
    Partial/noisy board counts such as 1 or 2 never create a street.
    """
    canonical = str(
        state.get("phase") or "WAITING"
    ).upper()

    try:
        count = int(local_board_count or 0)
    except (TypeError, ValueError):
        count = 0

    local_street = {
        3: "FLOP",
        4: "TURN",
        5: "RIVER",
    }.get(count)

    if local_street is None:
        return canonical

    rank = {
        "WAITING": -1,
        "PREFLOP": 0,
        "FLOP": 1,
        "TURN": 2,
        "RIVER": 3,
    }

    # Local perception may provisionally advance event attribution, but it
    # must never move events backward relative to confirmed canonical state.
    if rank.get(local_street, -1) > rank.get(canonical, -1):
        return local_street

    return canonical


def prechange_stack_observation(
    img,
    seat,
):
    """
    Read one preserved pre-change stack ROI.

    This exceptional path is used only to recover an unresolved canonical
    starting baseline. It performs perception only and assigns no poker
    semantics.
    """
    if img is None:
        return None

    region = (
        GEOM.get("stack_regions", {})
        .get(seat)
    )

    if not isinstance(region, dict):
        return None

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[
        y:y + h,
        x:x + w,
    ]

    if crop is None or crop.size == 0:
        return None

    result = read_stack_independent_consensus(
        crop
    )

    value = result.get("stack_bb")
    votes = int(result.get("votes") or 0)
    confidence = float(
        result.get("confidence") or 0.0
    )

    if (
        value is None
        or votes < 3
        or confidence < 0.95
    ):
        return None

    return {
        "observed_stack_bb": float(value),
        "confidence": confidence,
        "votes": votes,
        "mode": result.get(
            "mode",
            "independent_segmentation",
        ),
    }


def queue_one_startup_stack_async(
    state,
    frame_path,
    *,
    local_board_count=0,
):
    """
    Non-blocking replacement for retry_one_startup_stack().

    Queue at most one unresolved starting-stack baseline read. OCR executes
    exclusively in api_stack_worker. No action semantics are created here.
    """
    if not state.get("hand_token"):
        return state

    if local_board_count not in (0, None):
        return state

    now = time.time()

    last_attempt = float(
        state.get(
            "startup_stack_last_attempt_ts",
            0.0,
        )
        or 0.0
    )

    if (
        now - last_attempt
        < 0.25
    ):
        return state

    pending_transport = state.setdefault(
        "pending_stack_worker_requests",
        {},
    )

    # Never queue multiple startup-baseline OCR jobs concurrently.
    if any(
        item.get("purpose") == "baseline"
        for item in pending_transport.values()
    ):
        return state

    unresolved = list(
        state.get("pending_startup_stack_seats")
        or []
    )

    if not unresolved:
        return state

    seat = unresolved[0]

    request_id = queue_stack_worker_request(
        state,
        seat=seat,
        street=state.get(
            "phase",
            "PREFLOP",
        ),
        frame_path=str(frame_path or ""),
        purpose="baseline",
    )

    if request_id:
        state[
            "startup_stack_last_attempt_ts"
        ] = now

        print(
            "[STARTUP_STACK_ASYNC] queued",
            f"seat={seat}",
            f"request={request_id[:8]}",
            flush=True,
        )

    return state


def consume_startup_stack_worker_results(
    state,
    ready,
):
    """
    Consume completed baseline OCR without creating a betting action.

    Only trusted independent baseline evidence is allowed to promote the
    starting-stack cache.
    """
    ready = dict(ready or {})

    if not ready:
        return state

    retry_seats = list(
        state.get("pending_startup_stack_seats")
        or []
    )

    cache = state.setdefault(
        "starting_stack_cache",
        {},
    )

    for seat, item in ready.items():
        request = item.get("request") or {}
        result = item.get("result") or {}

        if request.get("purpose") != "baseline":
            continue

        independent = dict(
            result.get("independent") or {}
        )

        value = independent.get("stack_bb")
        confidence = float(
            independent.get("confidence")
            or 0.0
        )
        votes = int(
            independent.get("votes")
            or 0
        )

        trusted = (
            result.get("ok")
            and value is not None
            and confidence >= 0.90
            and votes >= 2
        )

        if trusted:
            cache[seat] = {
                "stack_bb": float(value),
                "stack_text": (
                    independent.get("stack_text")
                    or f"{float(value):g} BB"
                ),
                "confidence": confidence,
                "votes": votes,
                "mode": independent.get("mode"),
                "source": "async_startup_stack",
                "ts": result.get("ts")
                or time.time(),
            }

            retry_seats = [
                candidate
                for candidate in retry_seats
                if candidate != seat
            ]

            print(
                "[STARTUP_STACK_ASYNC] accepted",
                f"seat={seat}",
                f"stack={float(value):.2f}",
                f"confidence={confidence:.2f}",
                f"votes={votes}",
                flush=True,
            )

        else:
            print(
                "[STARTUP_STACK_ASYNC] retry",
                f"seat={seat}",
                f"value={value}",
                f"confidence={confidence:.2f}",
                f"votes={votes}",
                flush=True,
            )

    state["pending_startup_stack_seats"] = (
        retry_seats
    )

    return state


def retry_one_startup_stack(
    state,
    img,
    *,
    local_board_count=0,
):
    """
    Incrementally resolve one ambiguous starting stack from the current clean
    PREFLOP frame.

    This is perception-only recovery. It emits the existing trusted
    stack_baseline_observation event; CanonicalHand remains the sole owner of
    authoritative stack state.

    Only one unresolved seat is attempted per eligible cycle so startup
    recovery cannot turn into a serial OCR barrier on the live perception
    path.
    """
    pending = list(
        state.get("pending_startup_stack_seats")
        or []
    )

    if not pending:
        return state

    if (
        str(state.get("phase") or "WAITING").upper()
        != "PREFLOP"
    ):
        return state

    if int(local_board_count or 0) != 0:
        return state

    if state.get("terminal_action_frozen"):
        return state

    canonical_values = _canonical_stack_values()

    # Retire seats that have already been resolved by the snapshot, a prior
    # startup retry, or the ordinary action stack pipeline.
    pending = [
        seat
        for seat in pending
        if canonical_values.get(seat) is None
    ]

    state["pending_startup_stack_seats"] = pending

    if not pending:
        print(
            "[STARTUP_STACK_RETRY] complete",
            flush=True,
        )
        return state

    now = time.time()

    # Keep this deliberately paced. One local independent read every 250 ms
    # is enough to sample changing render/antialias states without making
    # stack OCR the coordinator's dominant hot-path cost.
    last_retry_ts = float(
        state.get("startup_stack_last_retry_ts")
        or 0.0
    )

    if now - last_retry_ts < 0.25:
        return state

    index = int(
        state.get("startup_stack_retry_index")
        or 0
    )

    if index >= len(pending):
        index = 0

    seat = pending[index]

    state["startup_stack_last_retry_ts"] = now

    baseline = prechange_stack_observation(
        img,
        seat,
    )

    if baseline is None:
        state["startup_stack_retry_index"] = (
            (index + 1) % len(pending)
        )

        print(
            "[STARTUP_STACK_RETRY] "
            f"seat={seat} result=unresolved "
            f"remaining={pending}",
            flush=True,
        )

        return state

    emit({
        "type": "stack_baseline_observation",
        "hand_token": state.get("hand_token"),
        "seat": seat,
        "observed_stack_bb": baseline[
            "observed_stack_bb"
        ],
        "confidence": baseline["confidence"],
        "votes": baseline["votes"],
        "mode": baseline["mode"],
        "origin_street": "PREFLOP",
        "source": "startup_retry",
    })

    pending.pop(index)
    state["pending_startup_stack_seats"] = pending

    if pending:
        state["startup_stack_retry_index"] = (
            index % len(pending)
        )
    else:
        state["startup_stack_retry_index"] = 0

    print(
        "[STARTUP_STACK_RESOLVED] "
        f"seat={seat} "
        f"stack={baseline['observed_stack_bb']:.2f} "
        f"confidence={baseline['confidence']:.2f} "
        f"votes={baseline['votes']} "
        f"remaining={pending}",
        flush=True,
    )

    return state


def close_pending_stack_candidate(
    state,
    pending,
    seat,
    reason="candidate_removed",
):
    """
    Remove one unresolved stack candidate and publish its closure.

    This publishes perception lifecycle only. Poker semantics remain
    downstream in the state machine / betting tracker.
    """
    entry = pending.pop(seat, None)

    if not entry:
        return None

    origin_street = str(
        entry.get("origin_street")
        or ""
    ).upper()

    emit({
        "type": "stack_candidate_closed",
        "hand_token": state.get("hand_token"),
        "seat": seat,
        "street": origin_street,
        "reason": reason,
        "sources": list(
            entry.get("trigger_sources") or []
        ),
    })

    # Transition-sourced absolute bet evidence is provisional only
    # while this seat's independent quantitative stack candidate can
    # still corroborate it. Once that candidate closes without a
    # validated stack transition, the provisional evidence has no
    # remaining corroboration owner and must not survive indefinitely.
    #
    # A validated transition closes the candidate before the ordinary
    # corroboration release runs, so preserve that success path here.
    if reason != "validated_stack_transition":
        deferred = state.setdefault(
            "deferred_bet_amount_results",
            {},
        )

        current_token = str(
            state.get("hand_token")
            or ""
        )

        for request_id, item in list(
            deferred.items()
        ):
            request = (
                item.get("request")
                or {}
            )
            result = (
                item.get("result")
                or {}
            )

            item_token = str(
                result.get("hand_token")
                or request.get("hand_token")
                or ""
            )

            item_seat = str(
                item.get("seat")
                or result.get("seat")
                or request.get("seat")
                or ""
            )

            item_street = str(
                item.get("street")
                or result.get("street")
                or request.get("street")
                or ""
            ).upper()

            source = str(
                request.get("source")
                or "transition"
            )

            if not (
                source == "transition"
                and current_token
                and item_token == current_token
                and item_seat == str(seat)
                and item_street == origin_street
            ):
                continue

            deferred.pop(
                request_id,
                None,
            )

            emit({
                "type": "provisional_bet_closed",
                "hand_token": item_token,
                "seat": item_seat,
                "street": item_street,
                "reason": "stack_candidate_uncorroborated",
                "source_request_id": request_id,
                "ts": time.time(),
            })

            print(
                "[BET_AMOUNT] retired deferred result "
                "reason=stack_candidate_uncorroborated "
                f"request={request_id[:8]} "
                f"seat={item_seat} "
                f"street={item_street}",
                flush=True,
            )

    return entry


def current_commitment_old_street_owing_seats(
    state,
    *,
    previous_street,
    next_street,
    fallback=None,
):
    """
    Return current old-street ownership for commitment attribution.

    Frame-local ownership is useful, but same-frame reconciliation may have
    refreshed the durable unresolved-boundary owner after that local snapshot
    was captured. Merge both sources so commitment attribution always sees
    the newest durable ownership without discarding valid frame-local context.
    """
    owing = set(
        fallback
        or []
    )

    owing.update(
        pending_boundary_old_street_owing_seats(
            state,
            previous_street=previous_street,
            next_street=next_street,
        )
    )

    return owing


def stack_candidate_must_remain_open_for_authoritative_owing(
    state,
    seat,
    entry,
    *,
    fallback_old_street_owing_seats=None,
    event_street=None,
):
    """
    Return True when an unresolved physical stack candidate still owns action
    on an authoritative unresolved old-street boundary.

    Retry budgets remain authoritative for ordinary/noise candidates. They may
    not, however, retire a real physical candidate while canonical chronology
    still says this actor owes action on the candidate's own street.
    """
    if not isinstance(entry, dict):
        return False

    candidate_street = str(
        entry.get("origin_street")
        or ""
    ).upper()

    if (
        not candidate_street
        or candidate_street == "WAITING"
    ):
        return False

    sources = set(
        entry.get("trigger_sources")
        or []
    )

    # Authoritative canonical owing may extend the lifetime of
    # independently corroborated physical commitment evidence, but it
    # must not turn raw stack motion into an immortal candidate.
    #
    # Motion-only candidates still receive the ordinary bounded
    # quantitative settlement/retry window. After trusted unchanged
    # stack reads, canonical "owing" is not independent evidence that
    # chips actually moved.
    if "bet_region_appeared" not in sources:
        return False

    next_street = str(
        event_street
        or state.get("phase")
        or candidate_street
    ).upper()

    owing = (
        current_commitment_old_street_owing_seats(
            state,
            previous_street=candidate_street,
            next_street=next_street,
            fallback=(
                fallback_old_street_owing_seats
            ),
        )
    )

    return str(seat) in owing


def commitment_evidence_street(
    state,
    changes,
    seat,
    fallback_street,
    *,
    old_street_owing_seats=None,
):
    """
    Return the immutable semantic street for seat-local commitment evidence.

    Precedence:
      1. validated stack detail from this frame;
      2. still-open physical stack candidate;
      3. active bet-region lifecycle owner;
      4. authoritative open canonical street when this actor still owes action;
      5. frame-local street fallback.

    Later board visibility and asynchronous worker completion must not
    relabel an already-started physical commitment. For genuinely new
    commitment evidence, provisional next-street visibility must not steal
    action ownership from an unfinished authoritative betting round.
    """
    fallback = str(
        fallback_street
        or state.get("phase")
        or "WAITING"
    ).upper()

    details = (
        getattr(
            changes,
            "stack_change_details",
            {},
        )
        or {}
    )

    detail = details.get(seat) or {}

    detail_street = str(
        detail.get("origin_street")
        or ""
    ).upper()

    if detail_street:
        return detail_street

    pending = (
        state.get("pending_stack_reads")
        or {}
    )

    entry = pending.get(seat) or {}

    candidate_street = str(
        entry.get("origin_street")
        or ""
    ).upper()

    if candidate_street:
        return candidate_street

    owners = (
        state.get("bet_region_street_owners")
        or {}
    )

    owner_street = str(
        owners.get(seat)
        or ""
    ).upper()

    if owner_street:
        return owner_street

    old_street_owing_seats = (
        current_commitment_old_street_owing_seats(
            state,
            previous_street=(
                state.get("phase")
                or "WAITING"
            ),
            next_street=fallback,
            fallback=old_street_owing_seats,
        )
    )

    canonical = str(
        state.get("phase")
        or "WAITING"
    ).upper()

    if (
        seat in old_street_owing_seats
        and canonical != "WAITING"
    ):
        return canonical

    return fallback


def stamp_bet_region_street_ownership(
    state,
    changes,
    fallback_street,
    *,
    old_street_owing_seats=None,
):
    """
    Attach immutable per-seat street ownership to physical bet-region
    transitions before bet sizing and observer ingestion.
    """
    transitions = dict(
        getattr(
            changes,
            "bet_region_transitions",
            {},
        )
        or {}
    )

    owners = state.setdefault(
        "bet_region_street_owners",
        {},
    )

    appeared = list(dict.fromkeys(
        getattr(
            changes,
            "bet_region_appeared",
            [],
        )
        or []
    ))

    cleared = list(dict.fromkeys(
        getattr(
            changes,
            "bet_region_cleared",
            [],
        )
        or []
    ))

    for seat in appeared:
        street = commitment_evidence_street(
            state,
            changes,
            seat,
            fallback_street,
            old_street_owing_seats=(
                old_street_owing_seats
            ),
        )

        owners[seat] = street

        payload = dict(
            transitions.get(seat)
            or {}
        )

        payload["origin_street"] = street
        transitions[seat] = payload

    for seat in cleared:
        street = commitment_evidence_street(
            state,
            changes,
            seat,
            fallback_street,
            old_street_owing_seats=(
                old_street_owing_seats
            ),
        )

        payload = dict(
            transitions.get(seat)
            or {}
        )

        payload["origin_street"] = street
        transitions[seat] = payload

    changes.bet_region_transitions = transitions

    return state


def emit_fast_actor_observations(
    state,
    changes,
    *,
    street=None,
):
    """
    Publish seat-attributed local chronology evidence immediately.

    This is intentionally independent of stack OCR, episode settlement,
    action classification, and bet sizing. A confirmed bet-region appearance
    proves that action has reached that seat.

    Same-frame stack-motion seats are attached as conservative blockers so
    chronology never skips through unresolved commitment evidence.
    """
    current_street = str(
        street
        or state.get("phase")
        or "WAITING"
    ).upper()

    if current_street == "WAITING":
        return

    if state.get("terminal_action_frozen"):
        return

    actor_seats = list(dict.fromkeys(
        getattr(changes, "bet_region_appeared", [])
        or []
    ))

    if not actor_seats:
        return

    same_frame_blockers = list(dict.fromkeys(
        getattr(changes, "stack_changed_seats", [])
        or []
    ))

    # Transition-sourced absolute bet evidence remains provisional
    # until the independent stack pipeline confirms commitment.
    #
    # Provisional does not mean passive. While same-hand/same-street
    # bet evidence is awaiting corroboration, chronology must not skip
    # through that seat and manufacture CHECK merely because no
    # canonical open bet has been established yet.
    deferred_bet_blockers = []
    pending_bet_blockers = []

    current_token = str(
        state.get("hand_token")
        or ""
    )

    # A transition-sourced bet read is chronology-owning from the moment
    # transport is queued, not only after its worker result returns.
    #
    # Otherwise a later observed actor can arrive during the asynchronous
    # transport gap and cause this still-unresolved seat to be fabricated
    # as a passive CHECK/FOLD before its quantitative evidence is available.
    for request in (
        state.get(
            "pending_bet_amount_requests"
        )
        or {}
    ).values():
        request_token = str(
            request.get("hand_token")
            or ""
        )

        request_street = str(
            request.get("street")
            or ""
        ).upper()

        request_seat = str(
            request.get("seat")
            or ""
        )

        source = str(
            request.get("source")
            or "transition"
        )

        if (
            request_seat
            and source == "transition"
            and current_token
            and request_token == current_token
            and request_street == current_street
        ):
            pending_bet_blockers.append(
                request_seat
            )

    for item in (
        state.get(
            "deferred_bet_amount_results"
        )
        or {}
    ).values():
        request = (
            item.get("request")
            or {}
        )

        result = (
            item.get("result")
            or {}
        )

        item_token = str(
            result.get("hand_token")
            or request.get("hand_token")
            or ""
        )

        item_street = str(
            result.get("street")
            or request.get("street")
            or item.get("street")
            or ""
        ).upper()

        item_seat = str(
            result.get("seat")
            or request.get("seat")
            or item.get("seat")
            or ""
        )

        source = str(
            request.get("source")
            or "transition"
        )

        if (
            item_seat
            and source == "transition"
            and current_token
            and item_token == current_token
            and item_street == current_street
        ):
            deferred_bet_blockers.append(
                item_seat
            )

    chronology_blockers = list(
        dict.fromkeys(
            same_frame_blockers
            + pending_bet_blockers
            + deferred_bet_blockers
        )
    )

    for seat in actor_seats:
        if not seat:
            continue

        emit({
            "type": "actor_observed",
            "hand_token": state.get("hand_token"),
            "seat": seat,
            "street": current_street,
            "source": "bet_region_appeared",
            "commitment_visible": True,
            "blocked_seats": chronology_blockers,
            "ts": time.time(),
        })

        print(
            "[ACTOR_OBSERVED_EMIT] "
            f"street={current_street} "
            f"seat={seat} "
            f"blocked={chronology_blockers}",
            flush=True,
        )


def emit_physical_actor_completions(
    changes,
    state,
    *,
    street=None,
):
    """
    Publish neutral seat-specific physical completion evidence.

    Opponent card disappearance proves that the seat's visible-card
    state completed, but does not itself assign FOLD. The state
    machine and betting-round tracker own chronological admission
    and poker semantics.
    """
    current_street = str(
        street
        or state.get("phase")
        or "WAITING"
    ).upper()

    if current_street == "WAITING":
        return

    if state.get("terminal_action_frozen"):
        return

    seats = list(dict.fromkeys(
        getattr(
            changes,
            "opponent_hole_cards_disappeared_seats",
            [],
        )
        or []
    ))

    for seat in seats:
        if not seat or seat == "hero":
            continue

        emit({
            "type": "physical_actor_completed",
            "hand_token": state.get("hand_token"),
            "seat": seat,
            "street": current_street,
            "source": "opponent_card_disappearance",
            "evidence": [
                "opponent_cards_visible_before",
                "opponent_cards_absent_after",
                "calibrated_acr_card_back",
            ],
            "ts": time.time(),
        })

        print(
            "[PHYSICAL_ACTOR_EMIT] "
            f"street={current_street} "
            f"seat={seat}",
            flush=True,
        )


def queue_stack_worker_request(
    state,
    *,
    seat,
    street,
    frame_path,
    purpose="settled",
):
    if not seat or not frame_path:
        return None

    # Settled stack transitions belong to an active canonical hand.
    #
    # A candidate may survive visually into the post-hand/reset frame, but
    # once coordinator state is WAITING or the hand token is gone it must not
    # create new quantitative transport carrying stale old-street semantics.
    #
    # Baseline/startup reads have a separate lifecycle and are intentionally
    # not subject to this guard.
    if (
        str(purpose or "settled") == "settled"
        and not state.get("hand_token")
    ):
        print(
            "[STACK_WORKER] skip unowned settled request "
            f"seat={seat} "
            f"street={str(street or 'WAITING').upper()} "
            f"phase={str(state.get('phase') or 'WAITING').upper()} "
            "reason=no_hand_token",
            flush=True,
        )
        return None

    if (
        str(purpose or "settled") == "settled"
        and _canonical_player_ineligible_for_settled_stack(seat)
    ):
        print(
            "[STACK_WORKER] skip ineligible settled request "
            f"seat={seat} "
            f"street={str(street or 'WAITING').upper()} "
            "reason=canonical_folded_or_inactive",
            flush=True,
        )
        return None

    request_id = uuid.uuid4().hex

    request = {
        "type": "stack_request",
        "request_id": request_id,
        "hand_token": state.get("hand_token"),
        "seat": seat,
        "street": str(
            street or "WAITING"
        ).upper(),
        "frame": str(frame_path),
        "purpose": str(
            purpose or "settled"
        ),
        "ts": time.time(),
    }

    append_jsonl(
        STACK_REQUESTS,
        request,
    )

    pending = state.setdefault(
        "pending_stack_worker_requests",
        {},
    )

    pending[request_id] = {
        "seat": request["seat"],
        "street": request["street"],
        "frame": request["frame"],
        "purpose": request["purpose"],
        "hand_token": request["hand_token"],
        "queued_ts": request["ts"],
    }

    log_latency(
        "queued",
        request_id=request_id,
        worker="stack",
        hand_token=request["hand_token"],
        seat=request["seat"],
        street=request["street"],
        purpose=request["purpose"],
        frame=request["frame"],
    )

    print(
        "[STACK_WORKER] queued",
        f"request={request_id[:8]}",
        f"seat={seat}",
        f"street={request['street']}",
        f"purpose={request['purpose']}",
        flush=True,
    )

    return request_id


def find_stack_worker_result(request_id):
    if (
        not request_id
        or not STACK_RESULTS.exists()
    ):
        return None

    try:
        lines = (
            STACK_RESULTS
            .read_text()
            .splitlines()
        )
    except Exception:
        return None

    for raw in reversed(lines):
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if (
            result.get("request_id")
            == request_id
        ):
            return result

    return None



def _replay_stack_request_release_ts(
    state,
    request_id,
    request,
    replay_records,
):
    """
    Return the first recorded timestamp on which an owned settled-stack
    request may affect replay semantics.

    Replay timing is derived exclusively from recorded candidate/sample time.
    Worker wall-clock completion never chooses this boundary.
    """
    if request.get("purpose") != "settled":
        return None

    seat = request.get("seat")

    entry = (
        state.get("pending_stack_reads")
        or {}
    ).get(seat) or {}

    if (
        entry.get("stack_worker_request_id")
        != request_id
    ):
        return None

    sample_ts = entry.get("last_stack_sample_ts")

    if sample_ts is None:
        return None

    sample_deadline = (
        float(sample_ts)
        + STACK_SETTLE_SECONDS
    )

    last_change_ts = entry.get("last_change_ts")

    candidate_deadline = (
        float(last_change_ts)
        + STACK_SETTLE_SECONDS
        if last_change_ts is not None
        else sample_deadline
    )

    deadline = max(
        sample_deadline,
        candidate_deadline,
    )

    for record in replay_records or []:
        record_ts = float(record["ts"])

        if record_ts + 1e-9 >= deadline:
            return record_ts

    return None


def replay_stack_semantic_barrier_allows_advance(
    state,
    *,
    next_frame_ts,
    replay_records,
):
    """
    Replay-only pre-capture barrier for already-owned settled-stack work.

    Before the deterministic semantic release frame, replay advances normally.
    At/after that boundary, the owning worker result must physically exist
    before another recorded frame may enter perception.
    """
    pending = (
        state.get("pending_stack_worker_requests")
        or {}
    )

    for request_id, request in pending.items():
        release_ts = _replay_stack_request_release_ts(
            state,
            request_id,
            request,
            replay_records,
        )

        if release_ts is None:
            continue

        if (
            float(next_frame_ts) + 1e-9
            < float(release_ts)
        ):
            continue

        if find_stack_worker_result(request_id) is None:
            return False

    return True


def reconcile_replay_stack_before_capture(
    state,
    *,
    current_frame_ts,
    next_frame_ts,
    replay_records,
):
    """
    Reconcile boundary-ready settled-stack results before the next replay
    frame enters LocalEventDetector.

    This helper is replay-only. Live capture remains fully asynchronous.
    """
    ready = collect_ready_stack_worker_results(
        state,
        replay_frame_ts=float(next_frame_ts),
        replay_records=replay_records,
    )

    settled = {
        seat: item
        for seat, item in ready.items()
        if (
            (item.get("request") or {}).get(
                "purpose"
            )
            == "settled"
        )
    }

    if not settled:
        # Collection and semantic reconciliation form one replay boundary.
        #
        # A settled result can physically arrive after the collector looked
        # but before replay_stack_semantic_barrier_allows_advance() performs
        # its own worker-result lookup. In that race, physical availability
        # must NOT authorize the next recorded perception frame: the result
        # has not yet passed through semantic reconciliation.
        #
        # Hold whenever an owned settled request is already due at this next
        # recorded frame. The next coordinator cycle remains on the same
        # replay boundary, allowing the collector to consume the now-ready
        # result before capture can advance.
        due_owned_settled = False

        pending_transport = (
            state.get("pending_stack_worker_requests")
            or {}
        )

        for request_id, request in pending_transport.items():
            if request.get("purpose") != "settled":
                continue

            release_ts = _replay_stack_request_release_ts(
                state,
                request_id,
                request,
                replay_records,
            )

            if release_ts is None:
                continue

            if (
                float(next_frame_ts) + 1e-9
                < float(release_ts)
            ):
                continue

            due_owned_settled = True
            break

        return {
            "advance": (
                False
                if due_owned_settled
                else replay_stack_semantic_barrier_allows_advance(
                    state,
                    next_frame_ts=float(next_frame_ts),
                    replay_records=replay_records,
                )
            ),
            "reconciled": False,
        }

    current_record = None

    for record in replay_records or []:
        if (
            abs(
                float(record["ts"])
                - float(current_frame_ts)
            )
            <= 1e-9
        ):
            current_record = record
            break

    if current_record is None:
        raise RuntimeError(
            "replay pre-capture reconciliation "
            "requires current recorded frame"
        )

    frame_path = str(
        current_record["frame_path"]
    )

    img = cv2.imread(frame_path)

    if img is None:
        raise RuntimeError(
            "replay pre-capture reconciliation "
            f"could not read frame: {frame_path}"
        )

    if img.shape[:2] != (696, 934):
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    changes = ChangeSet()

    # Pre-capture reconciliation is request-scoped, not a synthetic replay
    # perception cycle. The ordinary stack processor iterates every pending
    # candidate, so temporarily expose only candidates whose completed
    # settled-stack results are being reconciled at this boundary.
    #
    # Candidate dictionaries themselves are preserved by reference. After
    # processing, merge only those target seats back into the real pending
    # inventory. Unrelated candidates therefore receive no scheduling,
    # validation, retry, or lifetime mutation from this pre-capture operation.
    all_pending_reads = state.setdefault(
        "pending_stack_reads",
        {},
    )

    scoped_pending_reads = {
        seat: all_pending_reads[seat]
        for seat in settled
        if seat in all_pending_reads
    }

    state["pending_stack_reads"] = (
        scoped_pending_reads
    )

    try:
        process_stack_change_measurements_async(
            changes,
            img,
            state,
            stack_worker_results=settled,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            event_street=str(
                state.get("phase")
                or "WAITING"
            ).upper(),
            frame_path=frame_path,
            frame_ts=float(next_frame_ts),
            replay_records=replay_records,
        )
    finally:
        processed_pending_reads = (
            state.get("pending_stack_reads")
            or {}
        )

        for seat in settled:
            if seat in processed_pending_reads:
                all_pending_reads[seat] = (
                    processed_pending_reads[seat]
                )
            else:
                all_pending_reads.pop(
                    seat,
                    None,
                )

        state["pending_stack_reads"] = (
            all_pending_reads
        )

    # Processing an unchanged boundary-ready result establishes the
    # deterministic retry deadline/frame, but the ordinary async stack
    # processor would queue that retry on its next coordinator cycle.
    #
    # Replay must complete that ownership handoff before the boundary frame
    # enters perception, but it must NOT run every unrelated stack candidate
    # through a synthetic second processor cycle. Queue retries only for seats
    # whose results were reconciled above.
    pending_reads = (
        state.get("pending_stack_reads")
        or {}
    )

    for seat in settled:
        entry = pending_reads.get(seat)

        if not isinstance(entry, dict):
            continue

        # A validated/terminal result may have closed the candidate.
        if entry.get("stack_worker_request_id"):
            continue

        # Trusted unchanged quantitative evidence may deliberately
        # preserve semantic candidate ownership while disarming
        # expensive polling. Pre-capture replay must not manufacture
        # another request for that dormant candidate.
        if entry.get(
            "trusted_unchanged_polling_disarmed"
        ):
            continue

        retry_frame_path = entry.get(
            "retry_frame_path"
        )
        retry_frame_ts = entry.get(
            "retry_frame_ts"
        )
        retry_not_before_ts = entry.get(
            "retry_not_before_ts"
        )

        if (
            not retry_frame_path
            or retry_frame_ts is None
        ):
            continue

        if (
            retry_not_before_ts is not None
            and float(next_frame_ts) + 1e-9
            < float(retry_not_before_ts)
        ):
            continue

        request_id = queue_stack_worker_request(
            state,
            seat=seat,
            street=entry.get(
                "origin_street",
                state.get("phase", "WAITING"),
            ),
            frame_path=str(retry_frame_path),
            purpose="settled",
        )

        if not request_id:
            continue

        entry["stack_worker_request_id"] = (
            request_id
        )
        entry["last_stack_sample_ts"] = float(
            retry_frame_ts
        )

        entry.pop(
            "retry_not_before_ts",
            None,
        )
        entry.pop(
            "retry_frame_path",
            None,
        )
        entry.pop(
            "retry_frame_ts",
            None,
        )

    return {
        "advance": (
            replay_stack_semantic_barrier_allows_advance(
                state,
                next_frame_ts=float(next_frame_ts),
                replay_records=replay_records,
            )
        ),
        "reconciled": True,
        # Pre-capture reconciliation may validate a real quantitative stack
        # transition before the next recorded perception frame. Preserve that
        # semantic evidence for the ordinary replay observer/action pipeline
        # instead of allowing this temporary ChangeSet to disappear here.
        "semantic_changes": changes,
    }


def collect_ready_stack_worker_results(
    state,
    *,
    replay_frame_ts=None,
    replay_records=None,
    replay_eof=False,
):
    pending = state.setdefault(
        "pending_stack_worker_requests",
        {},
    )

    ready = {}

    for request_id, request in list(
        pending.items()
    ):
        result = find_stack_worker_result(
            request_id
        )

        if result is None:
            continue

        # Live mode preserves immediate asynchronous result consumption.
        #
        # Deterministic replay is different: worker wall-clock completion may
        # not choose the recorded frame on which candidate ownership mutates.
        # A settled result becomes semantically visible only on the first
        # recorded frame at/after the sampled frame's settlement deadline.
        if (
            replay_frame_ts is not None
            and replay_records
            and request.get("purpose") == "settled"
        ):
            seat = request.get("seat")

            entry = (
                state.get("pending_stack_reads")
                or {}
            ).get(seat) or {}

            sample_ts = entry.get(
                "last_stack_sample_ts"
            )

            if sample_ts is not None:
                # A completed settled-stack result may become semantically
                # visible only after BOTH:
                #
                #   1. the sampled frame has satisfied the quantitative
                #      settlement interval, and
                #   2. the physical candidate has itself stopped changing
                #      for the same interval.
                #
                # Otherwise collect_ready_stack_worker_results() can retire
                # durable transport ownership while the downstream stack
                # processor is still required to skip the candidate on its
                # last_change_ts settlement gate.
                sample_release_deadline = (
                    float(sample_ts)
                    + STACK_SETTLE_SECONDS
                )

                last_change_ts = entry.get(
                    "last_change_ts"
                )

                candidate_release_deadline = (
                    float(last_change_ts)
                    + STACK_SETTLE_SECONDS
                    if last_change_ts is not None
                    else sample_release_deadline
                )

                release_deadline = max(
                    sample_release_deadline,
                    candidate_release_deadline,
                )

                release_ts = None

                for record in replay_records:
                    record_ts = float(
                        record["ts"]
                    )

                    if (
                        record_ts
                        + 1e-9
                        >= release_deadline
                    ):
                        release_ts = record_ts
                        break

                # Ordinary replay may publish this completed result only
                # on a recorded frame at or beyond the semantic release
                # deadline.
                #
                # At replay EOF there may be no such later recorded frame.
                # EOF owns that finite-work boundary: a completed result may
                # proceed to the ordinary exact-request ownership checks
                # below, but only when the recording truly contains no
                # eligible semantic frame. This does not alter normal replay
                # timing and is never used by live capture.
                if release_ts is None:
                    if not replay_eof:
                        continue
                elif (
                    float(replay_frame_ts)
                    + 1e-9
                    < release_ts
                ):
                    continue

        # Settled-stack transport may be retired only when the semantic
        # candidate still owns this exact request. A completed worker result
        # that cannot yet be acknowledged must remain durably transport-owned
        # rather than disappearing between transport and candidate semantics.
        if request.get("purpose") == "settled":
            seat = request.get("seat")

            entry = (
                state.get("pending_stack_reads")
                or {}
            ).get(seat) or {}

            expected_request_id = entry.get(
                "stack_worker_request_id"
            )

            if expected_request_id != request_id:
                continue

        pending.pop(request_id, None)

        current_token = state.get(
            "hand_token"
        )

        if (
            request.get("hand_token")
            != current_token
            or result.get("hand_token")
            != current_token
        ):
            print(
                "[STACK_WORKER] ignored stale result",
                f"request={request_id[:8]}",
                flush=True,
            )
            continue

        seat = request.get("seat")

        if not seat:
            continue

        log_latency(
            "coordinator_consumed",
            request_id=request_id,
            worker="stack",
            hand_token=current_token,
            seat=seat,
            street=request.get("street"),
            purpose=request.get("purpose"),
            ok=result.get("ok"),
            elapsed_ms=result.get(
                "elapsed_ms"
            ),
        )

        ready[seat] = {
            "request_id": request_id,
            "request": request,
            "result": result,
        }

    return ready

def enrich_stack_change_measurements(
    changes,
    img,
    state,
    *,
    prechange_image=None,
    prior_occupied_bet_regions=None,
    prior_commitment_seats=None,
    response_to_aggression_seats=None,
    event_street=None,
    old_street_owing_seats=None,
    recent_stack_observations=None,
    frame_path="",
    frame_ts=None,
    stack_worker_results=None,
    queue_stack_ocr=False,
    replay_records=None,
    replay_eof=False,
):
    """
    Convert noisy stack-region movement into one settled quantitative
    transition.

    Raw stack changes are held until the region has remained quiet for
    STACK_SETTLE_SECONDS. Only then is that seat OCR-read and published as
    a STACK_CHANGED observation.
    """
    # Stack settlement is poker-semantic timing.
    #
    # Live mode falls back to wall time. Deterministic replay supplies the
    # recorded timestamp of the current frame so CPU/API latency cannot change
    # which replay frame crosses the settlement threshold.
    now = (
        float(frame_ts)
        if frame_ts is not None
        else time.time()
    )
    settle_seconds = STACK_SETTLE_SECONDS

    stack_worker_results = dict(
        stack_worker_results or {}
    )
    minimum_delta_bb = 0.05

    prior_occupied_bet_regions = set(
        prior_occupied_bet_regions or []
    )
    prior_commitment_seats = set(
        prior_commitment_seats or []
    )

    response_to_aggression_seats = set(
        response_to_aggression_seats or []
    )

    old_street_owing_seats = set(
        old_street_owing_seats or []
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

    # Deterministic bottom-strip/nameplate animation is useful
    # physical activity evidence, but it is not quantitative
    # evidence that the numeric stack changed.
    #
    # Keep stack_changed_seats untouched for legacy observation
    # semantics. Only exclude independently classified UI-only
    # activity from the expensive quantitative/OCR lane.
    ui_activity_seats = set(
        getattr(changes, "ui_activity_seats", [])
        or []
    )

    quantitative_motion_seats = [
        seat
        for seat in raw_changed_seats
        if seat not in ui_activity_seats
    ]

    # A confirmed bet-region appearance is independent evidence that this
    # seat may have committed chips. Schedule the same settled quantitative
    # stack read even when the stack pixel-motion detector missed the change.
    #
    # This is only an OCR trigger. It does NOT publish STACK_CHANGED; the
    # existing canonical comparison and validation path remains authoritative.
    bet_evidence_seats = list(
        getattr(changes, "bet_region_appeared", [])
        or []
    )

    candidate_seats = list(dict.fromkeys(
        quantitative_motion_seats + bet_evidence_seats
    ))

    pending = state.setdefault(
        "pending_stack_reads",
        {},
    )

    # Betting context can become authoritative after a physical stack
    # candidate has already opened. In particular, a responder's stack motion
    # may precede canonical publication of the aggression it is answering.
    #
    # Enrich existing same-street candidates with that later semantic context
    # before continuity resolution. This widens only the candidate search
    # window; final stack validation remains unchanged and authoritative.
    for pending_seat, pending_entry in pending.items():
        pending_street = str(
            pending_entry.get("origin_street")
            or ""
        ).upper()

        if (
            pending_seat in response_to_aggression_seats
            and pending_street
            == str(
                event_street
                or state.get("phase")
                or "WAITING"
            ).upper()
        ):
            pending_sources = set(
                pending_entry.get("trigger_sources")
                or []
            )

            if "response_to_aggression" not in pending_sources:
                pending_sources.add(
                    "response_to_aggression"
                )

                pending_entry["trigger_sources"] = sorted(
                    pending_sources
                )

                print(
                    "[STACK_CANDIDATE_CONTEXT] "
                    f"seat={pending_seat} "
                    f"street={pending_street} "
                    "added=response_to_aggression",
                    flush=True,
                )

    # Authoritative semantic commitment may become available after the
    # physical stack candidate opened and before its asynchronous OCR result
    # is reconciled. Once observed for the candidate's own street, preserve
    # that fact on the candidate so worker wall-clock completion cannot erase
    # semantic validation context.
    #
    # This is intentionally stronger than response_to_aggression. Response
    # context may widen continuity search, but only authoritative commitment
    # evidence may authorize final stack-transition validation.
    semantic_street = str(
        event_street
        or state.get("phase")
        or "WAITING"
    ).upper()

    for pending_seat, pending_entry in pending.items():
        pending_street = str(
            pending_entry.get("origin_street")
            or ""
        ).upper()

        if (
            pending_seat in prior_commitment_seats
            and pending_street
            and pending_street == semantic_street
        ):
            pending_entry[
                "semantic_commitment_confirmed"
            ] = True

    # CanonicalHand owns the authoritative stack baseline. The coordinator
    # reads it but never maintains a second persistent stack history.
    canonical_values = _canonical_stack_values()

    # Record quantitative-read candidates, but do not publish them yet.
    # Candidates may originate from raw stack motion or independent
    # bet-region evidence.
    for seat in candidate_seats:
        # One seat may perform successive physical commitments on adjacent
        # streets while an older weak stack-motion hypothesis is still
        # unresolved.
        #
        # Candidate persistence does not grant the old candidate ownership of
        # all future same-seat evidence. Once at least one trusted unchanged
        # stack read has failed to establish an old-street commitment, a fresh
        # bet-region onset on a genuinely newer physical street starts a new
        # commitment epoch.
        #
        # Do NOT split a candidate that has already established independent
        # commitment ownership. That candidate must retain its immutable onset
        # street even if asynchronous OCR settles after the board advances.
        existing_entry = pending.get(seat) or {}

        existing_street = str(
            existing_entry.get("origin_street")
            or ""
        ).upper()

        physical_street = str(
            event_street
            or state.get("phase")
            or "WAITING"
        ).upper()

        existing_sources = set(
            existing_entry.get("trigger_sources")
            or []
        )

        cross_street_new_commitment = bool(
            existing_entry
            and seat in bet_evidence_seats
            and "bet_region_appeared" not in existing_sources
            and existing_street
            and physical_street
            and existing_street != physical_street
            and not existing_entry.get(
                "semantic_commitment_confirmed"
            )
            and int(
                existing_entry.get(
                    "unchanged_stack_reads"
                )
                or 0
            ) > 0
        )

        if cross_street_new_commitment:
            close_pending_stack_candidate(
                state,
                pending,
                seat,
                reason="superseded_by_new_street_commitment",
            )

            print(
                "[STACK_CANDIDATE_EPOCH_SPLIT] "
                f"seat={seat} "
                f"old_street={existing_street} "
                f"new_street={physical_street} "
                "reason=fresh_cross_street_commitment",
                flush=True,
            )

        is_new_candidate = seat not in pending

        # A raw stack-motion transition gives us access to the immediately
        # preceding pixels before the detector advances its frame baseline.
        #
        # Recover that absolute pre-change stack only when:
        #   - this is the first frame of the pending episode;
        #   - the trigger is actual stack motion, not bet-region-only evidence;
        #   - CanonicalHand has no absolute baseline for this seat.
        #
        # The coordinator emits perception evidence only. The state machine
        # owns candidate matching and canonical promotion.
        if (
            is_new_candidate
            and seat in quantitative_motion_seats
            and canonical_values.get(seat) is None
            and prechange_image is not None
        ):
            baseline = prechange_stack_observation(
                prechange_image,
                seat,
            )

            if baseline is not None:
                emit({
                    "type": "stack_baseline_observation",
                    "seat": seat,
                    "observed_stack_bb": baseline[
                        "observed_stack_bb"
                    ],
                    "confidence": baseline[
                        "confidence"
                    ],
                    "votes": baseline["votes"],
                    "mode": baseline["mode"],
                    "origin_street": event_street,
                })

                print(
                    "[STACK_BASELINE_OBSERVATION] "
                    f"seat={seat} "
                    f"stack={baseline['observed_stack_bb']:.2f} "
                    f"votes={baseline['votes']} "
                    "source=prechange_stack_pixels",
                    flush=True,
                )

        entry = pending.setdefault(
            seat,
            {
                "first_change_ts": now,
                "last_change_ts": now,
                "max_mean_diff": 0.0,
                # Street belongs to candidate onset, not eventual OCR
                # settlement time. Local board visibility may provisionally
                # lead canonical confirmation for genuinely new next-street
                # actions. However, a seat that still owes action on the
                # confirmed old street must remain attached to that old street
                # across the visual boundary.
                "origin_street": (
                    physical_street
                    if cross_street_new_commitment
                    else commitment_evidence_street(
                        state,
                        changes,
                        seat,
                        (
                            event_street
                            or state.get(
                                "phase",
                                "WAITING",
                            )
                        ),
                        old_street_owing_seats=(
                            old_street_owing_seats
                        ),
                    )
                ),
                "trigger_sources": [],
            },
        )

        sources = set(entry.get("trigger_sources") or [])

        if seat in quantitative_motion_seats:
            sources.add("stack_motion")

        # A bet-region appearance is fresh either when this candidate
        # has never seen that evidence before, or when quantitative
        # polling was explicitly disarmed by a trusted unchanged read.
        #
        # trigger_sources is historical candidate provenance; it cannot
        # by itself distinguish a later physical edge from the original
        # edge that opened the candidate.
        fresh_commitment_evidence = bool(
            seat in bet_evidence_seats
            and (
                "bet_region_appeared" not in sources
                or entry.get(
                    "trusted_unchanged_polling_disarmed"
                )
            )
        )

        if seat in bet_evidence_seats:
            sources.add("bet_region_appeared")

        if seat in response_to_aggression_seats:
            sources.add("response_to_aggression")

        entry["trigger_sources"] = sorted(sources)
        entry["last_change_ts"] = now

        candidate_street = str(
            entry.get("origin_street")
            or ""
        ).upper()

        if (
            seat in prior_commitment_seats
            and candidate_street
            and candidate_street
            == str(
                event_street
                or state.get("phase")
                or "WAITING"
            ).upper()
        ):
            entry[
                "semantic_commitment_confirmed"
            ] = True

        # A candidate may begin from weak stack-motion evidence before chips
        # are actually committed. If stronger same-street bet-region evidence
        # arrives later, any retry frame selected from the earlier physical
        # episode is stale. Preserve candidate identity/street ownership, but
        # restart settlement scheduling from this newer commitment evidence.
        if (
            not is_new_candidate
            and fresh_commitment_evidence
        ):
            entry.pop(
                "retry_not_before_ts",
                None,
            )
            entry.pop(
                "retry_frame_path",
                None,
            )
            entry.pop(
                "retry_frame_ts",
                None,
            )
            entry.pop(
                "trusted_unchanged_polling_disarmed",
                None,
            )

            entry["unchanged_stack_reads"] = 0

            # Fresh commitment evidence starts a new semantic
            # sampling epoch. Any older worker may finish, but
            # subsequent quantitative sampling must never move
            # backward before this commitment-era frame.
            entry["sampling_floor_ts"] = now
            entry["sampling_floor_frame_path"] = str(
                frame_path
            )

            print(
                "[STACK_CANDIDATE_REARM] "
                f"seat={seat} "
                f"street={entry.get('origin_street')} "
                "reason=fresh_commitment_evidence",
                flush=True,
            )

        if is_new_candidate:
            print(
                "[STACK_CANDIDATE]",
                f"seat={seat}",
                f"sources={entry['trigger_sources']}",
                f"street={entry.get('origin_street')}",
                flush=True,
            )

            emit({
                "type": "stack_candidate_opened",
                "hand_token": state.get("hand_token"),
                "seat": seat,
                "street": entry.get("origin_street"),
                "sources": list(
                    entry.get("trigger_sources") or []
                ),
            })

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
    proposed_transitions = []

    for seat, entry in list(pending.items()):
        eof_completed_result = bool(
            replay_eof
            and seat in stack_worker_results
        )

        candidate_settled = bool(
            now - float(entry["last_change_ts"])
            >= settle_seconds
        )

        # Live and ordinary replay require the full semantic quiet
        # interval before quantitative stack sampling.
        #
        # Deterministic replay EOF is a finite-recording boundary:
        # recorded time can no longer advance. If a physically
        # evidenced candidate remains unresolved and owns no
        # outstanding worker, permit exactly the normal downstream
        # queue path to take one terminal sample. The queue path
        # below selects the newest recorded frame at EOF.
        eof_terminal_sample = bool(
            replay_eof
            and not candidate_settled
            and not eof_completed_result
            and not entry.get(
                "stack_worker_request_id"
            )
            and not entry.get(
                "eof_terminal_sample_consumed"
            )
            and bool(
                {
                    "stack_motion",
                    "bet_region_appeared",
                }
                & set(
                    entry.get(
                        "trigger_sources"
                    )
                    or []
                )
            )
        )

        if (
            not candidate_settled
            and not eof_completed_result
            and not eof_terminal_sample
        ):
            continue

        # A quantitative transition requires a trusted prior value from
        # the canonical hand state.
        previous = canonical_values.get(seat)
        if previous is None:
            # The asynchronous table snapshot may still be initializing the
            # canonical hand. Wait briefly for the authoritative starting
            # stack, but do not block forever if this seat never receives one.
            #
            # Replay EOF is a finite-recording boundary. Recorded time no
            # longer advances here, so the ordinary elapsed-time baseline
            # timeout can never mature. Without an authoritative prior stack
            # there is no valid quantitative transition to publish; retire
            # this candidate instead of retaining replay ownership forever.
            if replay_eof:
                print(
                    "[REPLAY_EOF_STACK_RETIRE] "
                    f"seat={seat} "
                    f"street={entry.get('origin_street')} "
                    "reason=baseline_unavailable_at_replay_eof",
                    flush=True,
                )

                close_pending_stack_candidate(
                    state,
                    pending,
                    seat,
                    reason="baseline_unavailable_at_replay_eof",
                )

                continue

            wait_attempts = int(
                entry.get("baseline_wait_attempts")
                or 0
            ) + 1
            entry["baseline_wait_attempts"] = wait_attempts

            if entry.get("baseline_wait_started_ts") is None:
                entry["baseline_wait_started_ts"] = now

            waited_seconds = (
                now
                - float(entry["baseline_wait_started_ts"])
            )

            if wait_attempts == 1 or wait_attempts % 10 == 0:
                print(
                    f"[STACK_SETTLE_WAIT] seat={seat} "
                    f"reason=canonical_baseline_not_ready "
                    f"attempt={wait_attempts} "
                    f"waited={waited_seconds * 1000.0:.1f}ms",
                    flush=True,
                )

            if waited_seconds >= maximum_pending_seconds:
                print(
                    f"[STACK_BASELINE_TIMEOUT] "
                    f"seat={seat} "
                    f"waited={waited_seconds * 1000.0:.1f}ms",
                    flush=True,
                )
                close_pending_stack_candidate(state, pending, seat)

            continue

        baseline_wait_started_ts = entry.pop(
            "baseline_wait_started_ts",
            None,
        )
        baseline_wait_attempts = int(
            entry.pop("baseline_wait_attempts", 0)
            or 0
        )

        if baseline_wait_started_ts is not None:
            waited_ms = (
                now
                - float(baseline_wait_started_ts)
            ) * 1000.0

            # Baseline waiting must not consume the independent OCR retry
            # budget. Begin that budget only after CanonicalHand is ready.
            entry["first_change_ts"] = now
            entry["ocr_attempts"] = 0

            print(
                f"[STACK_BASELINE_READY] seat={seat} "
                f"waited={waited_ms:.1f}ms "
                f"attempts={baseline_wait_attempts}",
                flush=True,
            )

        region = (
            GEOM.get("stack_regions", {})
            .get(seat)
        )

        if not region:
            close_pending_stack_candidate(
                state,
                pending,
                seat,
            )
            continue

        crop = None

        if queue_stack_ocr:
            worker_item = stack_worker_results.pop(
                seat,
                None,
            )

            if worker_item is None:
                # A request is already running. Never execute OCR or queue
                # duplicate work while capture continues.
                if entry.get("stack_worker_request_id"):
                    continue

                if entry.get(
                    "trusted_unchanged_polling_disarmed"
                ):
                    continue

                # Replay/live semantic retry gate.
                #
                # Worker completion may indicate that another quantitative
                # sample is needed, but completion latency must not itself
                # choose when the next sample is published. The candidate
                # carries an explicit semantic deadline.
                retry_not_before_ts = entry.get(
                    "retry_not_before_ts"
                )

                if (
                    retry_not_before_ts is not None
                    and now < float(retry_not_before_ts)
                    and not eof_terminal_sample
                ):
                    continue

                request_frame_path = frame_path
                request_frame_ts = now

                # EOF terminal sampling must use the newest recorded
                # evidence. A previously selected retry frame may
                # predate the candidate's final detected movement.
                if (
                    eof_terminal_sample
                    and replay_records
                ):
                    terminal_record = replay_records[-1]

                    request_frame_path = str(
                        terminal_record[
                            "frame_path"
                        ]
                    )

                    request_frame_ts = float(
                        terminal_record["ts"]
                    )

                    # Deterministic replay EOF owns exactly one
                    # terminal quantitative sample per physical
                    # stack candidate. Mark that finite opportunity
                    # before queueing so a completed unresolved
                    # result cannot level-trigger the same final
                    # recorded frame forever.
                    entry[
                        "eof_terminal_sample_consumed"
                    ] = True

                retry_frame_path = entry.get(
                    "retry_frame_path"
                )
                retry_frame_ts = entry.get(
                    "retry_frame_ts"
                )

                if (
                    not eof_terminal_sample
                    and replay_records
                    and retry_frame_path
                    and retry_frame_ts is not None
                ):
                    request_frame_path = str(
                        retry_frame_path
                    )
                    request_frame_ts = float(
                        retry_frame_ts
                    )

                sampling_floor_ts = entry.get(
                    "sampling_floor_ts"
                )
                sampling_floor_frame_path = entry.get(
                    "sampling_floor_frame_path"
                )

                if (
                    not eof_terminal_sample
                    and sampling_floor_ts is not None
                    and request_frame_ts
                    < float(sampling_floor_ts)
                ):
                    request_frame_ts = float(
                        sampling_floor_ts
                    )

                    if sampling_floor_frame_path:
                        request_frame_path = str(
                            sampling_floor_frame_path
                        )
                    elif replay_records:
                        floor_record = next(
                            (
                                record
                                for record in replay_records
                                if float(record["ts"])
                                + 1e-9
                                >= request_frame_ts
                            ),
                            None,
                        )

                        if floor_record is not None:
                            request_frame_path = str(
                                floor_record["frame_path"]
                            )
                            request_frame_ts = float(
                                floor_record["ts"]
                            )

                request_id = queue_stack_worker_request(
                    state,
                    seat=seat,
                    street=entry.get(
                        "origin_street",
                        state.get("phase", "WAITING"),
                    ),
                    frame_path=request_frame_path,
                    purpose="settled",
                )

                if request_id:
                    entry["stack_worker_request_id"] = (
                        request_id
                    )
                    entry["last_stack_sample_ts"] = (
                        request_frame_ts
                    )
                    entry.pop(
                        "retry_not_before_ts",
                        None,
                    )
                    entry.pop(
                        "retry_frame_path",
                        None,
                    )
                    entry.pop(
                        "retry_frame_ts",
                        None,
                    )

                continue

            result = worker_item.get("result") or {}

            expected_request_id = entry.get(
                "stack_worker_request_id"
            )

            if (
                expected_request_id
                and worker_item.get("request_id")
                != expected_request_id
            ):
                # Obsolete result from an earlier attempt.
                continue

            entry.pop(
                "stack_worker_request_id",
                None,
            )

            if result.get("ok"):
                reading = dict(
                    result.get("reading") or {}
                )
                independent = dict(
                    result.get("independent") or {}
                )
            else:
                reading = {}
                independent = {}

        else:
            # Legacy synchronous mode remains available to the existing
            # focused settlement regressions. Production main() will never
            # use this branch.
            crop = _crop_geometry_region(
                img,
                region,
            )

            if crop.size == 0:
                close_pending_stack_candidate(
                    state,
                    pending,
                    seat,
                )
                continue

            reading = read_stack(crop)
            independent = (
                read_stack_independent_consensus(
                    crop
                )
                or {}
            )

        # Resolve competing OCR candidates against the last trusted
        # canonical stack.
        #
        # OCR preprocessing variants are evidence, not independent votes.
        # In particular, correlated grayscale/Otsu agreement must not bypass
        # continuity when another OCR family exposes a conflicting candidate.
        raw_readings = reading.get("raw") or []

        candidate_values = [
            float(item["stack_bb"])
            for item in raw_readings
            if item.get("stack_bb") is not None
            and float(item["stack_bb"]) > 0.0
        ]

        # Add strong independent segmentation evidence before deciding
        # whether continuity resolution is needed. Previously the >=2
        # candidate gate considered only ordinary OCR, so a reliable
        # independent fallback could never make the resolver eligible.
        independent_value = independent.get(
            "stack_bb"
        )
        independent_votes = int(
            independent.get("votes") or 0
        )
        independent_confidence = float(
            independent.get("confidence") or 0.0
        )

        if (
            independent_value is not None
            and independent_votes >= 3
            and independent_confidence >= 0.95
        ):
            independent_value = float(
                independent_value
            )

            if (
                independent_value > 0.0
                and independent_value not in candidate_values
            ):
                candidate_values.append(
                    independent_value
                )

        unique_candidates = {
            round(value, 6)
            for value in candidate_values
        }

        # A single ordinary OCR candidate may still be authoritative when a
        # genuinely independent segmentation family strongly confirms the
        # exact same numeric value. This is confirmation, not disagreement
        # resolution, so it must happen before the >=2-candidate continuity
        # branch below.
        independent_confirms_ordinary = bool(
            independent_value is not None
            and independent_votes >= 3
            and independent_confidence >= 0.95
            and any(
                abs(
                    float(value)
                    - float(independent_value)
                )
                <= 0.001
                for value in (
                    float(item["stack_bb"])
                    for item in raw_readings
                    if item.get("stack_bb") is not None
                    and float(item["stack_bb"]) > 0.0
                )
            )
        )

        if (
            independent_confirms_ordinary
            and previous is not None
        ):
            confirmed_value = float(
                independent_value
            )

            previous_value = float(previous)

            has_commitment_evidence = bool(
                seat in bet_evidence_seats
                or seat in prior_occupied_bet_regions
                or seat in prior_commitment_seats
                or bool(
                    entry.get(
                        "semantic_commitment_confirmed"
                    )
                )
                or "bet_region_appeared"
                in set(entry.get("trigger_sources") or [])
                or "response_to_aggression"
                in set(entry.get("trigger_sources") or [])
            )

            maximum_drop_bb = (
                max(12.0, previous_value * 0.35)
                if has_commitment_evidence
                else 3.0
            )

            confirmed_delta = (
                previous_value - confirmed_value
            )

            if (
                confirmed_delta >= 0.0
                and confirmed_delta <= maximum_drop_bb
            ):
                reading["stack_bb"] = confirmed_value
                reading["stack_text"] = (
                    f"{confirmed_value:g} BB"
                )
                reading["confidence"] = max(
                    float(
                        reading.get("confidence")
                        or 0.0
                    ),
                    independent_confidence,
                )
                reading["votes"] = max(
                    int(reading.get("votes") or 0),
                    independent_votes,
                )
                reading["mode"] = (
                    "independent_confirmed"
                )

                print(
                    "[STACK_INDEPENDENT_CONFIRM] "
                    f"seat={seat} "
                    f"previous={previous_value:.2f} "
                    f"current={confirmed_value:.2f} "
                    f"delta={confirmed_delta:.2f} "
                    f"votes={independent_votes}",
                    flush=True,
                )

        if (
            previous is not None
            and len(unique_candidates) >= 2
        ):
            previous_value = float(previous)

            # Preserve the existing evidence-dependent continuity window.
            # Physical chip evidence permits a wider candidate search, but
            # this remains bounded and can only select a non-increasing stack.
            has_commitment_evidence = bool(
                seat in bet_evidence_seats
                or seat in prior_occupied_bet_regions
                or seat in prior_commitment_seats
                or bool(
                    entry.get(
                        "semantic_commitment_confirmed"
                    )
                )
                or "bet_region_appeared"
                in set(entry.get("trigger_sources") or [])
                or "response_to_aggression"
                in set(entry.get("trigger_sources") or [])
            )

            maximum_drop_bb = (
                max(12.0, previous_value * 0.35)
                if has_commitment_evidence
                else 3.0
            )

            if seat == "hero":
                print(
                    "[STACK_RESOLVER_INPUT] "
                    f"seat={seat} "
                    f"previous={previous_value:.2f} "
                    f"ordinary={reading.get('stack_bb')} "
                    f"ordinary_confidence={float(reading.get('confidence') or 0.0):.2f} "
                    f"ordinary_votes={int(reading.get('votes') or 0)} "
                    f"independent={independent_value} "
                    f"independent_confidence={independent_confidence:.2f} "
                    f"independent_votes={independent_votes} "
                    f"candidates={candidate_values} "
                    f"max_drop={maximum_drop_bb:.2f}",
                    flush=True,
                )

            resolution = resolve_stack_candidates(
                candidate_values,
                previous_stack_bb=previous_value,
                maximum_drop_bb=maximum_drop_bb,
            )

            if seat == "hero":
                print(
                    "[STACK_RESOLVER_OUTPUT] "
                    f"seat={seat} "
                    f"resolved={resolution.resolved} "
                    f"value={resolution.value} "
                    f"distance={resolution.distance} "
                    f"reason={resolution.reason}",
                    flush=True,
                )

            original_value = reading.get("stack_bb")

            if resolution.resolved:
                continuity_value = float(
                    resolution.value
                )

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
                    f"distance={float(resolution.distance or 0.0):.2f} "
                    f"reason={resolution.reason} "
                    f"candidates={candidate_values}",
                    flush=True,
                )
            else:
                # Candidate disagreement invalidates correlated-family
                # confidence. Preserve the provisional value for diagnostics,
                # but force the normal settlement retry path to reject it.
                reading["confidence"] = min(
                    float(reading.get("confidence") or 0.0),
                    0.50,
                )
                reading["votes"] = 1
                reading["mode"] = "continuity_unresolved"
                reading["numeric_evidence_present"] = bool(
                    resolution.numeric_evidence_present
                )
                reading["continuity_resolution_reason"] = (
                    resolution.reason
                )

                print(
                    f"[STACK_CONTINUITY_REJECT] seat={seat} "
                    f"previous={previous_value:.2f} "
                    f"resolver={original_value} "
                    f"reason={resolution.reason} "
                    f"distance={resolution.distance} "
                    f"max_drop={maximum_drop_bb:.2f} "
                    f"candidates={candidate_values}",
                    flush=True,
                )

        # Default for all result paths, including OCR failure.
        # The value is refined later only for trusted no_stack_change
        # results backed by physical candidate evidence.
        unchanged_physical_candidate = False

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
            unresolved_numeric_evidence = bool(
                reading.get("numeric_evidence_present")
                and reading.get(
                    "mode"
                )
                == "continuity_unresolved"
            )

            if unresolved_numeric_evidence:
                # Continuity rejected a real numeric family.
                # Keep it unresolved rather than consuming the
                # generic OCR-failure retry budget.
                #
                # This does not promote or accept the value.
                entry["last_numeric_evidence_ts"] = now
                entry[
                    "last_numeric_evidence_reason"
                ] = reading.get(
                    "continuity_resolution_reason"
                )

                reason = entry.get(
                    "last_numeric_evidence_reason"
                )

                print(
                    "[STACK_CONTINUITY_PENDING]",
                    "seat=" + str(seat),
                    "numeric=yes",
                    "resolved=no",
                    "ocr_budget_consumed=no",
                    "reason=" + str(reason),
                    flush=True,
                )

                continue

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
                close_pending_stack_candidate(state, pending, seat)


            # Persist failed Hero OCR crops for inspection.
            if (
                seat == "hero"
                and crop is not None
                and getattr(crop, "size", 0)
            ):
                out = ROOT / "runtime" / "stack_debug"
                out.mkdir(parents=True, exist_ok=True)

                ts = int(time.time() * 1000)

                cv2.imwrite(
                    str(out / f"{ts}_hero_stack.png"),
                    crop,
                )

            print(
                "[STACK_PIPELINE]",
                f"seat={seat}",
                "movement=yes",
                "validation=ocr_failed",
                "emitted=no",
                flush=True,
            )

            print(
                f"[STACK_SETTLE_SKIP] seat={seat} "
                f"reason=untrusted_read "
                f"confidence={confidence:.2f} "
                f"votes={votes} "
                f"attempt={attempts} "
                f"unchanged_physical={unchanged_physical_candidate} "
                f"retrying={retrying}",
                flush=True,
            )
            continue

        previous = float(previous)
        current = float(current)

        # Preserve trusted visual stack evidence independently from
        # canonical transition validation. In particular, an unchanged
        # trusted stack is valuable terminal evidence at a later street
        # boundary even though it must never emit stack_update here.
        if recent_stack_observations is not None:
            recent_stack_observations.add(
                seat=seat,
                stack_bb=current,
                confidence=confidence,
                votes=votes,
                mode=reading.get("mode", "unknown"),
                frame_path=str(frame_path or ""),
                ts=frame_ts if frame_ts is not None else now,
            )

        # Visual bet-region occupancy is detector evidence only.
        # It is sufficient to open an action episode, but not sufficient to
        # validate an extremely large OCR-derived stack commitment.
        #
        # Only semantically confirmed commitments may authorize a large stack
        # collapse.
        has_commitment_evidence = bool(
            seat in prior_commitment_seats
            or entry.get(
                "semantic_commitment_confirmed"
            )
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
            trigger_sources = set(
                entry.get("trigger_sources") or []
            )

            # A trusted unchanged stack is not a failed validation attempt
            # while a physically evidenced candidate is still developing.
            #
            # The visual transition may precede the numeric stack display by
            # several frames. Consuming validation_attempts here can exhaust
            # the candidate before the post-action stack is ever sampled.
            #
            # Keep sampling newer frames. Genuine validation failures still
            # consume the bounded retry budget below.
            unchanged_physical_candidate = bool(
                validation.reason == "no_stack_change"
                and bool(
                    {
                        "stack_motion",
                        "bet_region_appeared",
                    }
                    & trigger_sources
                )
            )

            # A trusted unchanged quantitative read is terminal for a
            # motion-only candidate. Raw stack-region motion is only a weak
            # hypothesis that the numeric stack changed; once trusted OCR
            # confirms the canonical value is unchanged, there is no
            # independent commitment evidence justifying another expensive
            # settled-stack read.
            #
            # Stronger candidates remain on the existing bounded retry path.
            # In particular, bet-region evidence may precede the displayed
            # numeric stack update and must retain its opportunity to settle.
            motion_only_unchanged = bool(
                validation.reason == "no_stack_change"
                and trigger_sources == {"stack_motion"}
                and not has_commitment_evidence
            )

            if motion_only_unchanged:
                close_pending_stack_candidate(
                    state,
                    pending,
                    seat,
                    reason="trusted_unchanged_motion_only",
                )

                print(
                    "[STACK_MOTION_ONLY_CLOSED] "
                    f"seat={seat} "
                    f"street={entry.get('origin_street')} "
                    f"previous={previous:.2f} "
                    f"current={current:.2f} "
                    "reason=trusted_unchanged_stack",
                    flush=True,
                )

                continue

            if unchanged_physical_candidate:
                # Candidate lifetime and OCR polling lifetime are
                # intentionally separate.
                #
                # Bet-region-originated candidates may become dormant after
                # one trusted unchanged read and wait for a genuinely fresh
                # physical edge to rearm them.
                #
                # response_to_aggression is different: it represents an
                # unresolved action obligation and may not produce another
                # distinct bet-region edge before the boundary must resolve.
                # Preserve the existing bounded retry behavior for that case.
                response_obligation = (
                    "response_to_aggression"
                    in trigger_sources
                )

                if not response_obligation:
                    entry.pop(
                        "retry_not_before_ts",
                        None,
                    )
                    entry.pop(
                        "retry_frame_path",
                        None,
                    )
                    entry.pop(
                        "retry_frame_ts",
                        None,
                    )
                    entry[
                        "trusted_unchanged_polling_disarmed"
                    ] = True

                    print(
                        "[STACK_POLLING_DISARMED] "
                        f"seat={seat} "
                        f"street={entry.get('origin_street')} "
                        f"sources={sorted(trigger_sources)} "
                        "reason=trusted_unchanged_stack",
                        flush=True,
                    )
                else:
                    last_sample_ts = entry.get(
                        "last_stack_sample_ts"
                    )

                    if last_sample_ts is not None:
                        retry_not_before_ts = (
                            float(last_sample_ts)
                            + settle_seconds
                        )

                        entry[
                            "retry_not_before_ts"
                        ] = retry_not_before_ts

                        if replay_records:
                            target_record = next(
                                (
                                    record
                                    for record in replay_records
                                    if float(record["ts"])
                                    >= retry_not_before_ts
                                ),
                                None,
                            )

                            if target_record is not None:
                                entry[
                                    "retry_frame_path"
                                ] = str(
                                    target_record["frame_path"]
                                )
                                entry[
                                    "retry_frame_ts"
                                ] = float(
                                    target_record["ts"]
                                )

            attempts = int(
                entry.get("validation_attempts")
                or 0
            )

            unchanged_stack_reads = int(
                entry.get(
                    "unchanged_stack_reads"
                )
                or 0
            )

            if unchanged_physical_candidate:
                unchanged_stack_reads += 1

                entry[
                    "unchanged_stack_reads"
                ] = unchanged_stack_reads

            else:
                attempts += 1
                entry["validation_attempts"] = attempts

            pending_age = (
                now - float(entry.get("first_change_ts") or now)
            )

            # Physical visual evidence can lead the displayed stack update.
            # A bet-region appearance is strong independent commitment
            # evidence, while stack motion is a weaker change candidate, but
            # either may legitimately precede a settled numeric stack delta.
            #
            # Therefore a trusted "no_stack_change" read does not immediately
            # disprove an already-open physical candidate. Keep it unresolved
            # only inside the existing bounded retry / age budget. This does
            # not authorize any wager or stack update; semantic validation
            # remains authoritative before emission.
            physical_candidate_pending = bool(
                validation.reason == "no_stack_change"
                and bool(
                    {
                        "stack_motion",
                        "bet_region_appeared",
                    }
                    & set(trigger_sources)
                )
            )

            # In asynchronous OCR mode, worker queue/execution latency must
            # not consume the semantic lifetime of a physically evidenced
            # stack candidate. Otherwise an unchanged first read can arrive
            # after maximum_pending_seconds and kill the candidate before a
            # newer post-action frame is ever sampled.
            #
            # The retry count remains the hard safety bound.
            within_lifetime = bool(
                queue_stack_ocr
                or pending_age < maximum_pending_seconds
            )

            authoritative_owing_lifetime = bool(
                unchanged_physical_candidate
                and stack_candidate_must_remain_open_for_authoritative_owing(
                    state,
                    seat,
                    entry,
                    fallback_old_street_owing_seats=(
                        old_street_owing_seats
                    ),
                    event_street=event_street,
                )
            )

            retrying = bool(
                (
                    validation.decision != STACK_REJECT
                    or physical_candidate_pending
                )
                and (
                    authoritative_owing_lifetime
                    or (
                        unchanged_physical_candidate
                        and unchanged_stack_reads
                        < maximum_ocr_attempts
                    )
                    or (
                        not unchanged_physical_candidate
                        and attempts
                        < maximum_ocr_attempts
                    )
                )
                and within_lifetime
            )

            if authoritative_owing_lifetime:
                print(
                    "[STACK_CANDIDATE_RETAIN] "
                    f"seat={seat} "
                    f"street={entry.get('origin_street')} "
                    "reason=authoritative_owing",
                    flush=True,
                )

            if not retrying:
                close_pending_stack_candidate(
                    state,
                    pending,
                    seat,
                )

            print(
                "[STACK_PIPELINE]",
                f"seat={seat}",
                f"movement=yes",
                f"validation={validation.reason}",
                "emitted=no",
                flush=True,
            )

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
        # A sub-threshold read does not by itself disprove the visual
        # stack candidate. The stack transition may still be developing
        # across frames. Preserve unresolved evidence while the existing
        # OCR retry / pending-age budget remains available.
        if delta < minimum_delta_bb:
            attempts = int(
                entry.get("ocr_attempts") or 0
            )
            pending_age = (
                now - float(
                    entry.get("first_change_ts")
                    or now
                )
            )

            retrying = (
                attempts < maximum_ocr_attempts
                and pending_age < maximum_pending_seconds
            )

            if not retrying:
                close_pending_stack_candidate(
                    state,
                    pending,
                    seat,
                    reason="subthreshold_exhausted",
                )

            print(
                "[STACK_PIPELINE]",
                f"seat={seat}",
                "movement=yes",
                "validation=no_stack_change",
                "emitted=no",
                f"retrying={retrying}",
                flush=True,
            )

            print(
                f"[STACK_SETTLE_SKIP] seat={seat} "
                f"previous={previous:.2f} current={current:.2f} "
                f"delta={delta:.2f} "
                f"reason=subthreshold_pending "
                f"retrying={retrying}",
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

        proposed_transitions.append({
            "seat": seat,
            "entry": entry,
            "measurement": measurement,
            "previous": previous,
            "current": current,
            "delta": delta,
            "confidence": confidence,
        })

    # Detect batch-wide OCR collapse before publishing any transition.
    #
    # A single large preflop commitment can be legitimate. Several different
    # seats apparently losing large portions of their stacks in the same
    # settlement cycle is not credible turn-by-turn poker action and was
    # observed when OCR read unrelated table numbers as stack values.
    phase = str(state.get("phase") or "WAITING").upper()

    large_preflop = [
        proposal
        for proposal in proposed_transitions
        if (
            phase == "PREFLOP"
            and float(proposal["delta"]) >= 8.0
        )
    ]

    contaminated_batch = (
        phase == "PREFLOP"
        and len(large_preflop) >= 3
    )

    if contaminated_batch:
        print(
            "[STACK_BATCH_REJECT] "
            f"phase={phase} "
            f"large_count={len(large_preflop)} "
            f"seats={[p['seat'] for p in large_preflop]} "
            f"deltas={[round(float(p['delta']), 2) for p in large_preflop]} "
            "reason=multi_seat_large_commitment_batch",
            flush=True,
        )

        # Keep proposals pending and wait for another settled visual read.
        # Bound retries so persistent corruption cannot create an OCR hot loop.
        for proposal in proposed_transitions:
            seat = proposal["seat"]
            entry = proposal["entry"]

            attempts = int(
                entry.get("batch_anomaly_attempts") or 0
            ) + 1

            entry["batch_anomaly_attempts"] = attempts
            entry["last_change_ts"] = now

            if attempts >= 3:
                close_pending_stack_candidate(state, pending, seat)

                print(
                    "[STACK_BATCH_DROP] "
                    f"seat={seat} "
                    f"attempts={attempts}",
                    flush=True,
                )

    else:
        for proposal in proposed_transitions:
            seat = proposal["seat"]
            measurement = proposal["measurement"]
            previous = proposal["previous"]
            current = proposal["current"]
            delta = proposal["delta"]
            confidence = proposal["confidence"]

            settled_details[seat] = measurement
            settled_seats.append(seat)

            print(
                "[STACK_PIPELINE]",
                f"seat={seat}",
                "movement=yes",
                f"sources={entry.get('trigger_sources') or []}",
                f"previous={previous:.2f}",
                f"current={current:.2f}",
                f"delta={delta:.2f}",
                f"confidence={confidence:.2f}",
                f"mode={measurement.get('stack_read_mode')}",
                "validation=PASS",
                "emitted=yes",
                flush=True,
            )

            # Publish the quantitative disposition before releasing the
            # chronology blocker. stack_candidate_closed causes the state
            # machine to replay preserved later-actor observations, so closing
            # first can fabricate a passive action for this seat before its
            # real commitment reaches canonical state.
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

            close_pending_stack_candidate(
                state,
                pending,
                seat,
                reason="validated_stack_transition",
            )

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


def process_stack_change_measurements_async(
    changes,
    img,
    state,
    *,
    stack_worker_results=None,
    prechange_image=None,
    prior_occupied_bet_regions=None,
    prior_commitment_seats=None,
    response_to_aggression_seats=None,
    event_street=None,
    old_street_owing_seats=None,
    recent_stack_observations=None,
    frame_path="",
    frame_ts=None,
    replay_records=None,
    replay_eof=False,
):
    """
    Production stack-settlement path.

    Candidate timing and semantic validation remain in the coordinator,
    but pixel OCR is exclusively performed by api_stack_worker.
    """
    ready = dict(
        stack_worker_results or {}
    )

    return enrich_stack_change_measurements(
        changes,
        img,
        state,
        prechange_image=prechange_image,
        prior_occupied_bet_regions=(
            prior_occupied_bet_regions
        ),
        prior_commitment_seats=(
            prior_commitment_seats
        ),
        response_to_aggression_seats=(
            response_to_aggression_seats
        ),
        event_street=event_street,
        old_street_owing_seats=(
            old_street_owing_seats
        ),
        recent_stack_observations=(
            recent_stack_observations
        ),
        frame_path=frame_path,
        frame_ts=frame_ts,
        stack_worker_results=ready,
        queue_stack_ocr=True,
        replay_records=replay_records,
        replay_eof=replay_eof,
    )


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


_PACED_REPLAY = None
_SCK_FRAME_SOURCE = None


def _paced_replay():
    global _PACED_REPLAY

    session = os.environ.get(
        "POKER_REPLAY_SESSION"
    )

    if not session:
        return None

    if _PACED_REPLAY is None:
        start_frame = int(
            os.environ.get(
                "POKER_REPLAY_START_FRAME",
                "1",
            )
        )

        end_text = os.environ.get(
            "POKER_REPLAY_END_FRAME"
        )

        end_frame = (
            int(end_text)
            if end_text
            else None
        )

        _PACED_REPLAY = PacedReplayCapture(
            session,
            start_frame=start_frame,
            end_frame=end_frame,
        )

        print(
            "[REPLAY_MODE] "
            f"session={session} "
            f"start={start_frame} "
            f"end={end_frame}",
            flush=True,
        )

    return _PACED_REPLAY


def capture_sck_live():
    global _SCK_FRAME_SOURCE

    if _SCK_FRAME_SOURCE is None:
        _SCK_FRAME_SOURCE = SCKFrameSource()
        _SCK_FRAME_SOURCE.connect()

        print(
            "[SCK_CAPTURE] connected persistent "
            "934x696 in-memory frame source",
            flush=True,
        )

    img = _SCK_FRAME_SOURCE.read()

    if img is None or img.size == 0:
        return None, None

    if img.shape[:2] != (696, 934):
        raise RuntimeError(
            "unexpected SCK frame shape "
            f"{img.shape}; expected (696, 934, 3)"
        )

    # Phase B contract:
    # ScreenCaptureKit acquisition is memory-only.
    #
    # Ordinary perception samples must never touch disk. A stable PNG
    # is materialized lazily only when an asynchronous worker requires
    # ownership of this exact frame.
    return img, None


def capture():
    global _CACHED_WINDOW

    replay = _paced_replay()

    if replay is not None:
        return replay.capture()

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


def materialize_worker_frame(
    img,
    *,
    purpose,
    request_id=None,
):
    """
    Persist one immutable canonical frame for asynchronous worker ownership.

    SCK acquisition remains entirely in memory. Disk I/O occurs only when a
    worker actually requires a filesystem path. Every materialization receives
    a unique filename so a later SCK sample can never overwrite pixels owned
    by an in-flight request.
    """
    if img is None or img.size == 0:
        return None

    CAPTURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    token = (
        str(request_id or uuid.uuid4().hex)
        .replace("/", "_")
        .replace(" ", "_")
    )

    safe_purpose = (
        str(purpose or "worker")
        .replace("/", "_")
        .replace(" ", "_")
    )

    frame_path = (
        CAPTURE_DIR
        / f"acr_table_sck_{safe_purpose}_{token}.png"
    )

    ok = cv2.imwrite(
        str(frame_path),
        img,
    )

    if not ok:
        raise RuntimeError(
            "could not materialize SCK worker frame "
            f"{frame_path}"
        )

    return frame_path


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

        starting_roster_seats = []

        starting_roster_frame = result.get("canonical_frame")
        starting_roster_image = (
            cv2.imread(str(starting_roster_frame))
            if starting_roster_frame
            else None
        )

        if starting_roster_image is not None:
            starting_roster_image = cv2.resize(
                starting_roster_image,
                (934, 696),
            )

            starting_roster_seats = occupied_seats(
                starting_roster_image,
                GEOM,
            )

        bootstrap = HeroBootstrap.initialize_hand(
            result=result,
            participant_collector=PARTICIPANT_COLLECTOR,
            hand_token=request_token,
            frozen_ts=time.time(),
            starting_roster_seats=starting_roster_seats,
        )

        cards = bootstrap["hero_cards"]
        validation_error = bootstrap["validation_error"]

        if validation_error:
            print(
                f"[HERO] rejected worker result "
                f"reason={validation_error}"
            )
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

        frozen_participants = bootstrap["frozen_participants"]
        starting_roster_seats = bootstrap["starting_roster_seats"]
        dealer = bootstrap["dealer"]
        positions = bootstrap["positions"]

        print(
            f"[PARTICIPANT_FREEZE_PUBLISH] "
            f"dealt_count={len(frozen_participants)} "
            f"dealt_seats={frozen_participants} "
            f"roster_count={len(starting_roster_seats)} "
            f"roster_seats={starting_roster_seats}",
            flush=True,
        )

        # Publish Hero cards immediately and start the asynchronous snapshot
        # pipeline before serial local stack OCR. Stack enrichment continues
        # below while the snapshot worker runs in parallel.
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

        if not state.get("snapshot_cached"):
            emit({
                "type": "snapshot_request",
                "source_request_id": pending_id,
                "hand_token": request_token,
                "canonical_frame": result.get("canonical_frame"),
                # Hand-start physical occupancy owns poker topology.
                # Card-back participant evidence remains diagnostic only;
                # an early fold may already have removed visible card backs.
                "roster_seats": list(starting_roster_seats),
                "dealt_in_seats": list(starting_roster_seats),
            })
            state["snapshot_cached"] = True

        # Seed the fast table context with local stack OCR from the same
        # canonical Hero-card frame. GPT remains deferred name enrichment.
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

        local_players = bootstrap_local_stacks(
            canonical_image=canonical_image,
            frozen_participants=starting_roster_seats,
            geometry=GEOM,
            crop_geometry_region=_crop_geometry_region,
            stack_reader=read_stack,
        )

        unresolved_startup_stacks = [
            player.get("seat")
            for player in local_players
            if (
                player.get("seat")
                and player.get("stack_bb") is None
            )
        ]

        state["pending_startup_stack_seats"] = list(
            dict.fromkeys(unresolved_startup_stacks)
        )
        state["startup_stack_retry_index"] = 0
        state["startup_stack_last_retry_ts"] = 0.0

        if unresolved_startup_stacks:
            print(
                "[STARTUP_STACK_PENDING] "
                f"seats={unresolved_startup_stacks}",
                flush=True,
            )

        participant_evidence = (
            PARTICIPANT_COLLECTOR.snapshot()
        )

        # Hand-start physical occupancy owns immutable poker topology.
        #
        # Card-back evidence remains useful diagnostic evidence, but it may
        # already be narrower after an immediate fold and therefore must not
        # remove a starting player from positions or action chronology.
        if starting_roster_seats:
            emit({
                "type": "table_context",
                "hand_token": request_token,
                "participant_frame_count": int(
                    participant_evidence.get("frame_count")
                    or 0
                ),
                "roster_seats": list(starting_roster_seats),
                "dealt_in_seats": list(starting_roster_seats),
                "card_back_dealt_in_seats": list(frozen_participants),
                "dealer_button_seat": dealer["dealer_button_seat"],
                "positions": positions,
                "hero_position": positions.get(
                    "hero",
                    "unknown",
                ),
                "players": local_players,
            })
        else:
            print(
                "[TABLE_CONTEXT_DEFER] "
                f"hand_token={request_token} "
                f"participant_frames={int(participant_evidence.get('frame_count') or 0)} "
                "reason=participant_roster_not_frozen",
                flush=True,
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


def load_betting_round_status():
    """
    Read the state machine's authoritative betting obligation artifact.

    Failure or partial writes are nonfatal. A missing/invalid artifact means
    there is no safe basis for retrospective boundary work.
    """
    if not BETTING_ROUND_STATUS.exists():
        return {}

    try:
        value = json.loads(
            BETTING_ROUND_STATUS.read_text()
        )
    except Exception:
        return {}

    return value if isinstance(value, dict) else {}


def event_log_next_cursor():
    """
    Return the next-unprocessed api_events.jsonl index.

    This is transport chronology only. It assigns no poker semantics.
    """
    if not EVENT_LOG.exists():
        return 0

    try:
        return len(
            EVENT_LOG.read_text().splitlines()
        )
    except Exception:
        return 0


def pending_boundary_old_street_owing_seats(
    state,
    *,
    previous_street,
    next_street,
):
    """
    Return authoritative old-street owing ownership retained by the
    currently unresolved physical street boundary.

    This is fallback ownership only. A newer valid betting-round status may
    refresh the set on any later frame of the same boundary.
    """
    pending = (
        state.get("pending_boundary_route")
        if isinstance(state, dict)
        else None
    )

    if not isinstance(pending, dict):
        return set()

    hand_token = str(
        state.get("hand_token")
        or ""
    )

    if (
        not hand_token
        or str(
            pending.get("hand_token")
            or ""
        ) != hand_token
    ):
        return set()

    if (
        str(
            pending.get("previous_street")
            or ""
        ).upper()
        != str(previous_street or "").upper()
    ):
        return set()

    if (
        str(
            pending.get("next_street")
            or ""
        ).upper()
        != str(next_street or "").upper()
    ):
        return set()

    return {
        str(seat)
        for seat in (
            pending.get(
                "old_street_owing_seats"
            )
            or []
        )
        if seat
    }


def refresh_boundary_old_street_owing_seats(
    state,
    *,
    previous_street,
    next_street,
    status,
):
    """
    Return the causally authoritative old-street owing set for a physical
    board boundary.

    Previously acknowledged boundary ownership is durable. A matching
    betting-round status may replace it only when its processed event cursor
    is at least as fresh as the boundary's causal ownership watermark.

    Authoritative owing is defined consistently as the union of
    players_owing_action and canonical_players_to_act.
    """
    retained = pending_boundary_old_street_owing_seats(
        state,
        previous_street=previous_street,
        next_street=next_street,
    )

    status = (
        status
        if isinstance(status, dict)
        else {}
    )

    current_token = str(
        state.get("hand_token")
        or ""
    )

    status_token = str(
        status.get("hand_token")
        or ""
    )

    status_street = str(
        status.get("street")
        or ""
    ).upper()

    expected_street = str(
        previous_street
        or ""
    ).upper()

    if (
        not current_token
        or status_token != current_token
        or status_street != expected_street
    ):
        return retained

    pending = (
        state.get("pending_boundary_route")
        or {}
    )

    same_boundary = bool(
        isinstance(pending, dict)
        and str(
            pending.get("hand_token")
            or ""
        ) == current_token
        and str(
            pending.get("previous_street")
            or ""
        ).upper() == expected_street
        and str(
            pending.get("next_street")
            or ""
        ).upper()
        == str(
            next_street
            or ""
        ).upper()
    )

    freshness_floor = None

    if same_boundary:
        required_cursor = pending.get(
            "required_event_cursor"
        )

        last_acknowledged_cursor = pending.get(
            "last_acknowledged_event_cursor"
        )

        if required_cursor is not None:
            freshness_floor = int(
                required_cursor
            )
        elif last_acknowledged_cursor is not None:
            freshness_floor = int(
                last_acknowledged_cursor
            )

    try:
        status_cursor = int(
            status.get(
                "processed_event_cursor"
            )
            or 0
        )
    except Exception:
        status_cursor = 0

    if (
        freshness_floor is not None
        and status_cursor < freshness_floor
    ):
        return retained

    players_owing = {
        str(seat)
        for seat in (
            status.get(
                "players_owing_action"
            )
            or []
        )
        if seat
    }

    canonical_to_act = {
        str(seat)
        for seat in (
            status.get(
                "canonical_players_to_act"
            )
            or []
        )
        if seat
    }

    return (
        players_owing
        | canonical_to_act
    )


def maybe_route_acknowledged_boundary(state):
    """
    Route a preserved physical street boundary only after authoritative
    betting status acknowledges every coordinator event published through
    old-street reconciliation.

    This function never waits or sleeps. If acknowledgement is not ready,
    the boundary remains pending for a later coordinator cycle.
    """
    pending = (
        state.get("pending_boundary_route")
        if isinstance(state, dict)
        else None
    )

    if not isinstance(pending, dict):
        return state, None

    hand_token = str(
        state.get("hand_token") or ""
    )

    pending_token = str(
        pending.get("hand_token") or ""
    )

    if (
        not hand_token
        or pending_token != hand_token
    ):
        state["pending_boundary_route"] = None
        return state, None

    previous_street = str(
        pending.get("previous_street") or ""
    ).upper()

    next_street = str(
        pending.get("next_street") or ""
    ).upper()

    required_cursor = pending.get(
        "required_event_cursor"
    )

    # This physical boundary has not yet completed its same-frame
    # quantitative reconciliation.
    if required_cursor is None:
        return state, None

    required_cursor = int(required_cursor)

    status = load_betting_round_status()

    status_token = str(
        (status or {}).get("hand_token") or ""
    )

    status_street = str(
        (status or {}).get("street") or ""
    ).upper()

    try:
        acknowledged_cursor = int(
            (status or {}).get(
                "processed_event_cursor"
            )
            or 0
        )
    except Exception:
        acknowledged_cursor = 0

    if (
        status_token != hand_token
        or status_street != previous_street
        or acknowledged_cursor < required_cursor
    ):
        print(
            "[BOUNDARY_ACK_WAIT] "
            f"street={previous_street} "
            f"next={next_street} "
            f"required={required_cursor} "
            f"ack={acknowledged_cursor}",
            flush=True,
        )

        return state, None

    if bool(
        status.get(
            "boundary_can_skip_stack_ocr"
        )
    ):
        if pending.get(
            "passive_result_emitted"
        ):
            # The zero-OCR result already entered the authoritative
            # event stream. Preserve physical boundary ownership until
            # the state machine consumes it and publishes a newer
            # acknowledged status.
            return state, None

        request_id = (
            "passive-"
            + str(uuid.uuid4())[:8]
        )

        payload = {
            "type": "boundary_stack_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "street": previous_street,
            "next_street": next_street,
            "observations": [],
            "ts": time.time(),
        }

        # Unlike real boundary workers, this result has no asynchronous
        # transport owner. The router therefore owns publication.
        emit(payload)

        pending[
            "passive_result_emitted"
        ] = True

        pending[
            "passive_result_request_id"
        ] = request_id

        pending[
            "last_acknowledged_event_cursor"
        ] = acknowledged_cursor

        # The emitted result itself must now be acknowledged before this
        # physical boundary can make another routing decision.
        pending[
            "required_event_cursor"
        ] = event_log_next_cursor()

        state[
            "pending_boundary_route"
        ] = pending

        print(
            "[BOUNDARY_STACK_OCR_SKIP] "
            f"request={request_id[:16]} "
            f"street={previous_street} "
            f"next={next_street} "
            "reason=authoritative_clean_postflop_boundary "
            "emitted=yes",
            flush=True,
        )

        state[
            "last_boundary_request_key"
        ] = (
            f"{hand_token}:"
            f"{previous_street}:"
            f"{next_street}:"
            "passive"
        )

    else:
        state, payload = maybe_queue_boundary_stack_request(
            state,
            previous_street=previous_street,
            next_street=next_street,
            frames=list(
                pending.get("frames") or []
            ),
            status=status,
        )

    # Cursor acknowledgement establishes that the state machine has consumed
    # coordinator events through this boundary. It does NOT by itself mean
    # the authoritative old betting round has completed.
    #
    # Preserve physical old-street ownership while canonical poker state
    # still reports actors owing action. Later acknowledged status may shrink
    # or clear this set; only authoritative completion retires the boundary.
    owing = {
        str(seat)
        for seat in (
            status.get("players_owing_action")
            or []
        )
        if seat
    }

    canonical_to_act = {
        str(seat)
        for seat in (
            status.get("canonical_players_to_act")
            or []
        )
        if seat
    }

    authoritative_owing = (
        owing
        | canonical_to_act
    )

    round_complete = bool(
        status.get("complete")
    )

    betting_open = bool(
        status.get("betting_open")
    )

    if (
        not round_complete
        and (
            betting_open
            or authoritative_owing
        )
    ):
        pending[
            "old_street_owing_seats"
        ] = sorted(
            authoritative_owing
        )

        # This ACK has been consumed. Keep the physical boundary alive, but
        # require the next coordinator publication boundary to arm a fresh
        # cursor before another authoritative routing decision.
        pending[
            "last_acknowledged_event_cursor"
        ] = acknowledged_cursor

        pending[
            "required_event_cursor"
        ] = None

        state["pending_boundary_route"] = pending

        print(
            "[BOUNDARY_ACK_RETAIN] "
            f"street={previous_street} "
            f"next={next_street} "
            f"required={required_cursor} "
            f"ack={acknowledged_cursor} "
            f"owing={sorted(authoritative_owing)} "
            f"queued={bool(payload)}",
            flush=True,
        )

        return state, payload

    state["pending_boundary_route"] = None

    print(
        "[BOUNDARY_ACK_RELEASE] "
        f"street={previous_street} "
        f"next={next_street} "
        f"required={required_cursor} "
        f"ack={acknowledged_cursor} "
        f"queued={bool(payload)}",
        flush=True,
    )

    return state, payload


def provisional_response_context_seats(
    state,
    *,
    hand_token,
    street,
    candidate_seats,
):
    """
    Return pending stack-candidate seats that may use the wider
    continuity SEARCH window while an earlier same-hand/same-street
    transition bet remains unresolved.

    Provisional aggression is context only. It does not publish the
    bet, classify the candidate's action, or authorize final semantic
    stack validation.
    """
    state = (
        state
        if isinstance(state, dict)
        else {}
    )

    expected_token = str(
        hand_token or ""
    )

    expected_street = str(
        street or ""
    ).upper()

    candidates = {
        str(seat)
        for seat in (
            candidate_seats or []
        )
        if seat
    }

    if (
        not expected_token
        or not expected_street
        or expected_street == "WAITING"
        or not candidates
    ):
        return set()

    aggressors = set()

    for item in (
        state.get(
            "deferred_bet_amount_results"
        )
        or {}
    ).values():
        if not isinstance(item, dict):
            continue

        request = (
            item.get("request")
            or {}
        )

        result = (
            item.get("result")
            or {}
        )

        source = str(
            request.get("source")
            or "transition"
        )

        item_token = str(
            result.get("hand_token")
            or request.get("hand_token")
            or ""
        )

        item_street = str(
            result.get("street")
            or request.get("street")
            or item.get("street")
            or ""
        ).upper()

        item_seat = str(
            result.get("seat")
            or request.get("seat")
            or item.get("seat")
            or ""
        )

        if (
            source == "transition"
            and item_seat
            and item_token == expected_token
            and item_street == expected_street
        ):
            aggressors.add(
                item_seat
            )

    if not aggressors:
        return set()

    # Chronology blockers already prevent later actors from crossing
    # unresolved provisional aggression. This helper supplies only
    # numeric continuity-search context to a different pending seat.
    return {
        seat
        for seat in candidates
        if seat not in aggressors
    }


def stack_response_context(
    status,
    *,
    hand_token,
    street,
    seat,
):
    """
    Interpret state-machine betting status for read-only stack
    continuity-search context.

    This does not authorize a stack transition or poker action.
    """
    status = (
        status
        if isinstance(status, dict)
        else {}
    )

    expected_token = str(
        hand_token or ""
    )

    expected_street = str(
        street or ""
    ).upper()

    status_token = str(
        status.get("hand_token") or ""
    )

    status_street = str(
        status.get("street")
        or status.get("current_street")
        or ""
    ).upper()

    authoritative = bool(
        expected_token
        and expected_street
        and status_token == expected_token
        and status_street == expected_street
    )

    betting_open = bool(
        status.get("betting_open")
    ) if authoritative else False

    owing = set(
        status.get("players_owing_action")
        or []
    ) if authoritative else set()

    owes_response = bool(
        authoritative
        and betting_open
        and seat in owing
    )

    return {
        "authoritative": authoritative,
        "betting_open": betting_open,
        "owes_response": owes_response,
    }


def maybe_queue_boundary_stack_request(
    state,
    *,
    previous_street,
    next_street,
    frames,
    status=None,
):
    """
    Queue retrospective stack OCR only at a valid local street advance.

    This function is routing only. It performs no OCR and assigns no poker
    semantics. The state-machine betting status is authoritative for which
    seats still owed action on the street that just ended.
    """
    previous_street = str(
        previous_street or "WAITING"
    ).upper()

    next_street = str(
        next_street or previous_street
    ).upper()

    valid_advance = {
        ("PREFLOP", "FLOP"),
        ("FLOP", "TURN"),
        ("TURN", "RIVER"),
    }

    if (previous_street, next_street) not in valid_advance:
        return state, None

    hand_token = str(
        state.get("hand_token") or ""
    )

    if not hand_token:
        return state, None

    if status is None:
        status = load_betting_round_status()

    status_token = str(
        (status or {}).get("hand_token") or ""
    )

    status_street = str(
        (status or {}).get("street") or ""
    ).upper()

    if status_token != hand_token:
        return state, None

    if status_street != previous_street:
        return state, None

    seats = list(dict.fromkeys(
        (status or {}).get("players_owing_action")
        or []
    ))

    if not seats:
        return state, None

    request_key = (
        f"{hand_token}:{previous_street}"
    )

    if (
        state.get("last_boundary_stack_request_key")
        == request_key
    ):
        return state, None

    usable_frames = []

    for item in list(frames or []):
        frame_path = str(
            (item or {}).get("frame_path") or ""
        )

        if not frame_path:
            continue

        usable_frames.append({
            "ts": (item or {}).get("ts"),
            "frame_path": frame_path,
            "local_board_count": int(
                (item or {}).get(
                    "local_board_count",
                    0,
                )
                or 0
            ),
        })

    if not usable_frames:
        return state, None

    request_id = uuid.uuid4().hex

    payload = {
        "type": "boundary_stack_request",
        "request_id": request_id,
        "hand_token": hand_token,
        "street": previous_street,
        "next_street": next_street,
        "boundary_ts": time.time(),
        "seats": seats,
        "frames": usable_frames,
    }

    append_jsonl(
        BOUNDARY_STACK_REQUESTS,
        payload,
    )

    state[
        "last_boundary_stack_request_key"
    ] = request_key

    print(
        "[BOUNDARY_STACK_REQUEST] "
        f"request={request_id[:8]} "
        f"street={previous_street} "
        f"next={next_street} "
        f"seats={seats} "
        f"frames={len(usable_frames)}",
        flush=True,
    )

    return state, payload


def queue_board_request(
    state,
    expected_len,
    frame,
    *,
    replay_frame_ts=None,
):
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
    state["board_request_ts"] = queued_ts
    state["board_request_replay_frame_ts"] = (
        float(replay_frame_ts)
        if replay_frame_ts is not None
        else None
    )

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
    state["board_request_replay_frame_ts"] = None

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

    confirmed_board = list(
        state.get("confirmed_board") or []
    )

    if confirmed_board:
        prefix_len = min(
            len(confirmed_board),
            confirmed,
        )

        expected_prefix = confirmed_board[:prefix_len]
        observed_prefix = board_to_emit[:prefix_len]

        if observed_prefix != expected_prefix:
            contradiction = (
                state.get(
                    "board_prefix_contradiction"
                )
                or {}
            )

            contradiction_board = list(
                contradiction.get("board")
                or []
            )

            contradiction_expected_len = (
                contradiction.get(
                    "expected_len"
                )
            )

            contradiction_confirmed_len = (
                contradiction.get(
                    "confirmed_len"
                )
            )

            # Repair is deliberately narrow:
            #
            # - canonical board already has a shorter prefix
            # - this result is exactly the next street
            # - a prior independently requested result returned
            #   the exact same longer board
            #
            # One contradictory API response can never rewrite
            # confirmed board ownership.
            repeated_longer_contradiction = (
                expected_len
                == confirmed + 1
                and contradiction_expected_len
                == expected_len
                and contradiction_confirmed_len
                == confirmed
                and contradiction_board
                == list(board_to_emit)
            )

            if repeated_longer_contradiction:
                print(
                    "[BOARD_PREFIX_REPAIRED] "
                    f"confirmed={expected_prefix} "
                    f"repaired={observed_prefix} "
                    f"board={board_to_emit} "
                    f"expected_len={expected_len}",
                    flush=True,
                )

                state[
                    "board_prefix_contradiction"
                ] = None

            else:
                state[
                    "board_prefix_contradiction"
                ] = {
                    "board": list(
                        board_to_emit
                    ),
                    "expected_len":
                        expected_len,
                    "confirmed_len":
                        confirmed,
                }

                print(
                    "[BOARD] prefix mutation rejected "
                    f"confirmed={expected_prefix} "
                    f"observed={observed_prefix} "
                    f"expected_len={expected_len} "
                    "contradiction_saved=True",
                    flush=True,
                )

                return state, False

        else:
            # A valid prefix disproves any outstanding contradiction
            # against this confirmed board.
            state[
                "board_prefix_contradiction"
            ] = None

    state["confirmed_board"] = list(board_to_emit)
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


def maybe_read_board(
    state,
    count,
    frame,
    *,
    replay_frame_ts=None,
):
    if state.get("phase") == "WAITING":
        return state

    pending_id = state.get("board_request_id")

    if pending_id:
        result = find_board_result(pending_id)

        if result is None:
            # Deterministic replay owns this request until its worker result
            # physically resolves. Wall-clock latency must never retire the
            # request and cause a later recorded frame to queue replacement
            # board work.
            if (
                state.get(
                    "board_request_replay_frame_ts"
                )
                is not None
            ):
                return state

            request_ts = state.get(
                "board_request_ts"
            )
            now = time.time()

            pending_seconds = (
                now - float(request_ts)
                if request_ts is not None
                else 0.0
            )

            if (
                request_ts is None
                or pending_seconds
                < BOARD_REQUEST_TIMEOUT_SECONDS
            ):
                return state

            print(
                "[BOARD] pending request timed out "
                f"request={pending_id[:8]} "
                f"after={pending_seconds:.1f}s",
                flush=True,
            )

            # Retire coordinator ownership only. Any late result from this
            # request is no longer authoritative. Current local board
            # perception may immediately queue replacement work.
            state["board_request_id"] = None
            state["board_request_expected_len"] = None
            state["board_request_ts"] = None
            state["board_request_replay_frame_ts"] = None

        else:
            log_latency(
                "coordinator_consumed",
                request_id=pending_id,
                worker="board",
                ok=result.get("ok"),
                elapsed_ms=result.get("elapsed_ms"),
                expected_len=result.get("expected_len"),
            )

            state, _ = apply_board_result(
                state,
                result,
            )

            state["board_request_ts"] = None
            return state

    confirmed = state.get(
        "confirmed_board_len",
        0,
    )

    if count not in (3, 4, 5):
        return state

    if count <= confirmed:
        return state

    expected_next = (
        3
        if confirmed == 0
        else confirmed + 1
    )

    if expected_next not in (3, 4, 5):
        return state

    now = time.time()

    last_attempt = state.get(
        "last_api_attempt_ts",
        0,
    )

    if now - last_attempt < 1.25:
        return state

    state["last_api_attempt_ts"] = now

    return queue_board_request(
        state,
        expected_next,
        frame,
        replay_frame_ts=replay_frame_ts,
    )



def queue_initial_bet_inventory(
    state,
    frame,
    frame_path,
):
    """
    Recover opponent wagers that are already visible when observation begins.

    Static geometry is only the gating signal. Exact numeric sizing remains
    asynchronous API perception.

    Hero is deliberately excluded because Hero cards/UI contaminate the Hero
    bet ROI at hand start.
    """
    if state.get("initial_bet_inventory_done"):
        return state

    # One-shot by contract. Even a malformed frame must not schedule this
    # continuously on every capture.
    state["initial_bet_inventory_done"] = True

    if frame is None or frame.size == 0:
        print(
            "[BET_INITIAL_INVENTORY] "
            "skipped reason=empty_frame",
            flush=True,
        )
        return state

    if not state.get("hand_token"):
        print(
            "[BET_INITIAL_INVENTORY] "
            "skipped reason=no_hand_token",
            flush=True,
        )
        return state

    try:
        canonical = to_canonical_frame(
            frame,
            GEOM,
        )

        static = bet_region_occupancy(
            canonical,
            GEOM,
            baseline=None,
        )

    except Exception as exc:
        print(
            "[BET_INITIAL_INVENTORY] "
            f"failed error={exc}",
            flush=True,
        )
        return state

    queued = []

    for seat, info in static.items():
        # Hero static occupancy is known to be contaminated by cards/UI.
        if seat == "hero":
            continue

        if not bool(
            (info or {}).get(
                "legacy_occupied",
                False,
            )
        ):
            continue

        state = queue_bet_amount_request(
            state,
            frame_path,
            seat,
            "PREFLOP",
            source="initial_inventory",
        )

        queued.append(seat)

    print(
        "[BET_INITIAL_INVENTORY] "
        f"queued={queued}",
        flush=True,
    )

    return state


def queue_bet_amount_request(
    state,
    frame,
    seat,
    street,
    source="transition",
):
    """
    Queue an asynchronous absolute visible-bet read.

    This is perception evidence only. It does not classify the
    poker action and does not mutate CanonicalHand.
    """
    if frame is None or not seat:
        return state

    request_id = uuid.uuid4().hex

    request = {
        "type": "bet_amount_request",
        "request_id": request_id,
        "hand_token": state.get("hand_token"),
        "seat": seat,
        "street": str(
            street
            or state.get("phase")
            or "UNKNOWN"
        ).upper(),
        "frame": str(frame),
        "source": str(source or "transition"),
        "ts": time.time(),
    }

    append_jsonl(
        BET_AMOUNT_REQUESTS,
        request,
    )

    pending = state.setdefault(
        "pending_bet_amount_requests",
        {},
    )

    pending[request_id] = {
        "hand_token": request["hand_token"],
        "seat": request["seat"],
        "street": request["street"],
        "frame": request["frame"],
        "source": request["source"],
        "queued_ts": request["ts"],
    }

    log_latency(
        "queued",
        request_id=request_id,
        worker="bet_amount",
        hand_token=request["hand_token"],
        seat=request["seat"],
        street=request["street"],
        frame=request["frame"],
    )

    print(
        "[BET_AMOUNT] queued",
        f"request={request_id[:8]}",
        f"seat={request['seat']}",
        f"street={request['street']}",
        f"source={request['source']}",
        flush=True,
    )

    return state


def find_bet_amount_result(request_id):
    if (
        not request_id
        or not BET_AMOUNT_RESULTS.exists()
    ):
        return None

    try:
        lines = (
            BET_AMOUNT_RESULTS
            .read_text()
            .splitlines()
        )
    except Exception:
        return None

    for line in reversed(lines):
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue

        if (
            result.get("request_id")
            == request_id
        ):
            return result

    return None


def emit_bet_amount_observation(
    state,
    request_id,
    request,
    result,
    bet_bb,
):
    current_token = state.get("hand_token")

    emit({
        "type": "bet_amount_observation",
        "hand_token": current_token,
        "seat": result.get("seat"),
        "street": result.get("street"),
        "bet_bb": round(float(bet_bb), 2),
        "source": request.get(
            "source",
            "transition",
        ),
        "source_request_id": request_id,
        "frame": result.get("frame"),
        "elapsed_ms": result.get(
            "elapsed_ms"
        ),
        "ts": result.get("ts")
        or time.time(),
    })

    log_latency(
        "coordinator_consumed",
        request_id=request_id,
        worker="bet_amount",
        hand_token=current_token,
        seat=result.get("seat"),
        street=result.get("street"),
        ok=True,
        elapsed_ms=result.get("elapsed_ms"),
    )

    print(
        "[BET_AMOUNT] observed",
        f"seat={result.get('seat')}",
        f"street={result.get('street')}",
        f"bet={float(bet_bb):.2f}",
        f"request={request_id[:8]}",
        f"source={request.get('source', 'transition')}",
        flush=True,
    )


def release_corroborated_bet_amount_results(
    state,
    changes,
):
    """
    Release deferred transition-sourced absolute bet reads only after the
    quantitative stack pipeline confirms that the same seat actually
    committed chips on the same street.

    This does not perform poker-action classification. It validates only
    that the local visual transition corresponded to a real chip commitment.
    """
    deferred = state.setdefault(
        "deferred_bet_amount_results",
        {},
    )

    if not deferred:
        return state

    current_token = state.get("hand_token")

    # Hand ownership is independent of stack corroboration.
    # Retire stale provisional evidence even on a frame with
    # no confirmed quantitative stack transition.
    for request_id, item in list(deferred.items()):
        request = item.get("request") or {}
        result = item.get("result") or {}

        item_token = (
            request.get("hand_token")
            or result.get("hand_token")
        )

        if (
            item_token
            and item_token != current_token
        ):
            seat = (
                item.get("seat")
                or result.get("seat")
                or request.get("seat")
            )

            street = str(
                item.get("street")
                or result.get("street")
                or request.get("street")
                or ""
            ).upper()

            emit({
                "type": "provisional_bet_closed",
                "hand_token": item_token,
                "seat": seat,
                "street": street,
                "reason": "hand_changed",
                "source_request_id": request_id,
                "ts": time.time(),
            })

            deferred.pop(
                request_id,
                None,
            )

            print(
                "[BET_AMOUNT] retired deferred result "
                "reason=hand_changed "
                f"request={request_id[:8]}",
                flush=True,
            )

    if not deferred:
        return state

    details = dict(
        getattr(
            changes,
            "stack_change_details",
            {},
        )
        or {}
    )

    confirmed_seats = set(
        getattr(
            changes,
            "stack_changed_seats",
            [],
        )
        or []
    )

    if not confirmed_seats:
        return state

    for request_id, item in list(deferred.items()):
        seat = item.get("seat")

        if seat not in confirmed_seats:
            continue

        detail = details.get(seat) or {}

        try:
            delta_bb = float(
                detail.get("delta_bb")
            )
        except (TypeError, ValueError):
            continue

        if delta_bb <= 0.0:
            continue

        result = item.get("result") or {}
        request = item.get("request") or {}

        result_street = str(
            result.get("street")
            or request.get("street")
            or ""
        ).upper()

        stack_street = str(
            detail.get("origin_street")
            or ""
        ).upper()

        if (
            result_street
            and stack_street
            and result_street != stack_street
        ):
            # Candidate origin_street remains historical: an unresolved
            # old-street physical candidate must not be relabeled merely
            # because newer board-local evidence appeared.
            #
            # However, independently confirmed quantitative stack evidence
            # may validate a newer-street deferred absolute bet when both
            # independent sensors agree on the exact chip commitment.
            #
            # Keep this bridge deliberately narrow. Weak continuity OCR or
            # merely approximate amounts may not cross a street boundary.
            try:
                deferred_bet_bb = float(
                    item.get("bet_bb")
                )
            except (TypeError, ValueError):
                deferred_bet_bb = None

            try:
                stack_confidence = float(
                    detail.get(
                        "stack_read_confidence"
                    )
                    or 0.0
                )
            except (TypeError, ValueError):
                stack_confidence = 0.0

            stack_mode = str(
                detail.get(
                    "stack_read_mode"
                )
                or ""
            ).lower()

            independent_modes = {
                "independent_confirmed",
                "independent_segmentation",
                "agreement_verified",
            }

            exact_quantitative_match = bool(
                deferred_bet_bb is not None
                and abs(
                    deferred_bet_bb
                    - delta_bb
                ) <= 0.011
            )

            strong_independent_stack = bool(
                stack_confidence >= 0.95
                and stack_mode
                in independent_modes
            )

            if not (
                exact_quantitative_match
                and strong_independent_stack
            ):
                continue

            print(
                "[BET_AMOUNT] cross-boundary corroboration "
                f"seat={seat} "
                f"stack_street={stack_street} "
                f"bet_street={result_street} "
                f"delta={delta_bb:.2f} "
                f"bet={deferred_bet_bb:.2f} "
                f"confidence={stack_confidence:.2f} "
                f"mode={stack_mode}",
                flush=True,
            )

        emit_bet_amount_observation(
            state,
            request_id,
            request,
            result,
            item["bet_bb"],
        )

        deferred.pop(request_id, None)

        emit({
            "type": "provisional_bet_closed",
            "hand_token": state.get("hand_token"),
            "seat": seat,
            "street": result_street,
            "reason": "corroborated",
            "source_request_id": request_id,
            "ts": time.time(),
        })

        print(
            "[BET_AMOUNT] corroborated",
            f"seat={seat}",
            f"street={result_street}",
            f"delta={delta_bb:.2f}",
            f"request={request_id[:8]}",
            flush=True,
        )

    return state


def apply_bet_amount_result(
    state,
    result,
):
    request_id = result.get("request_id")

    pending = state.setdefault(
        "pending_bet_amount_requests",
        {},
    )

    request = pending.pop(
        request_id,
        None,
    )

    if request is None:
        return state, False

    result_token = result.get("hand_token")
    current_token = state.get("hand_token")

    if (
        not current_token
        or not result_token
        or result_token != current_token
    ):
        print(
            "[BET_AMOUNT] ignored stale result "
            "from another hand",
            flush=True,
        )
        return state, False

    if not result.get("ok"):
        print(
            "[BET_AMOUNT] worker result failed",
            f"seat={result.get('seat')}",
            f"street={result.get('street')}",
            f"error={result.get('error') or 'unknown'}",
            flush=True,
        )
        return state, False

    try:
        bet_bb = float(
            result.get("bet_bb")
        )
    except (TypeError, ValueError):
        print(
            "[BET_AMOUNT] invalid numeric result",
            f"value={result.get('bet_bb')!r}",
            flush=True,
        )
        return state, False

    if not 0.0 < bet_bb <= 1000.0:
        print(
            "[BET_AMOUNT] result out of range",
            f"value={bet_bb}",
            flush=True,
        )
        return state, False

    source = str(
        request.get("source")
        or "transition"
    )

    # The initial inventory deliberately recovers wagers that were already
    # present when observation began. No stack transition is guaranteed to
    # remain observable, so a valid numeric API read is sufficient there.
    if source == "initial_inventory":
        emit_bet_amount_observation(
            state,
            request_id,
            request,
            result,
            bet_bb,
        )
        return state, True

    # Transition-sourced reads are provisional until the independent stack
    # pipeline confirms a positive commitment by this seat. A bet-region
    # appearance alone is not trustworthy enough to publish numeric evidence.
    deferred = state.setdefault(
        "deferred_bet_amount_results",
        {},
    )

    deferred[request_id] = {
        "request": dict(request),
        "result": dict(result),
        "bet_bb": round(bet_bb, 2),
        "seat": result.get("seat"),
        "street": result.get("street"),
    }

    emit({
        "type": "provisional_bet_opened",
        "hand_token": current_token,
        "seat": result.get("seat"),
        "street": result.get("street"),
        "source": source,
        "source_request_id": request_id,
        "bet_bb": round(bet_bb, 2),
        "ts": result.get("ts")
        or time.time(),
    })

    print(
        "[BET_AMOUNT] deferred",
        f"seat={result.get('seat')}",
        f"street={result.get('street')}",
        f"bet={bet_bb:.2f}",
        f"request={request_id[:8]}",
        "reason=awaiting_stack_corroboration",
        flush=True,
    )

    return state, True


def queue_pot_request(
    state,
    frame,
    purpose="observation",
    forced_pot_baseline_bb=None,
):
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
    state["pot_request_purpose"] = str(
        purpose or "observation"
    )
    state["pot_request_forced_baseline_bb"] = (
        float(forced_pot_baseline_bb)
        if forced_pot_baseline_bb is not None
        else None
    )

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

    request_purpose = state.get(
        "pot_request_purpose"
    ) or "observation"

    forced_pot_baseline_bb = state.get(
        "pot_request_forced_baseline_bb"
    )

    state["pot_request_id"] = None
    state["pot_request_ts"] = None
    state["pot_request_purpose"] = None
    state["pot_request_forced_baseline_bb"] = None

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

    is_terminal = bool(
        state.get("terminal_pot_pending")
        and request_id
        == state.get("terminal_pot_request_id")
    )

    emit({
        "type": "pot_update",
        "pot_bb": round(pot_bb, 2),
        "raw_text": result.get("raw_text"),
        "source_request_id": request_id,
        "confidence": result.get("confidence"),
        "terminal": is_terminal,
        "purpose": request_purpose,
        "forced_pot_baseline_bb": forced_pot_baseline_bb,
    })

    print(
        f"[POT] observed={pot_bb:.2f} BB "
        f"raw={result.get('raw_text')!r}",
        flush=True,
    )

    return state, True



def ready_outgoing_stack_reconciliation_exists(
    state,
):
    """
    Return True when the current/outgoing street still owns an exactly
    correlated completed settled-stack result.

    This is an ordering predicate only. It does not retire transport or
    reconcile stack semantics. The normal stack pipeline retains ownership.
    """
    current_street = str(
        state.get("phase")
        or "WAITING"
    ).upper()

    pending_reads = (
        state.get("pending_stack_reads")
        or {}
    )

    transport = (
        state.get("pending_stack_worker_requests")
        or {}
    )

    for request_id, request in transport.items():
        if request.get("purpose") != "settled":
            continue

        request_street = str(
            request.get("street")
            or ""
        ).upper()

        if request_street != current_street:
            continue

        seat = request.get("seat")

        entry = pending_reads.get(seat)

        if not isinstance(entry, dict):
            continue

        if (
            entry.get("stack_worker_request_id")
            != request_id
        ):
            continue

        result = find_stack_worker_result(
            request_id
        )

        if result is None:
            continue

        if (
            result.get("request_id")
            != request_id
        ):
            continue

        return True

    return False


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

        if (
            board_result is not None
            and ready_outgoing_stack_reconciliation_exists(
                state
            )
        ):
            # Preserve durable board ownership. Completed quantitative
            # evidence from the outgoing street must reconcile before the
            # next-street board can mutate coordinator street state.
            board_result = None

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

    # Bet-amount reads are multi-request by design. Several seats may
    # commit before the API worker completes an earlier request.
    pending_bet_requests = dict(
        state.get(
            "pending_bet_amount_requests"
        )
        or {}
    )

    for request_id in pending_bet_requests:
        bet_result = find_bet_amount_result(
            request_id
        )

        if bet_result is None:
            continue

        state, _ = apply_bet_amount_result(
            state,
            bet_result,
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
        completed_phase = state.get(
            "last_hero_action_complete_phase"
        )

        # Hero-card disappearance can classify a fold only while Hero's
        # completed decision still belongs to an unfinished betting round.
        #
        # Once the authoritative betting tracker says this street is complete
        # and nobody owes action, Hero cannot subsequently fold on that same
        # street. Card disappearance at that point belongs to street/hand
        # transition evidence, not another poker action.
        betting_status = load_betting_round_status()

        status_street = str(
            betting_status.get("street")
            or betting_status.get("current_street")
            or ""
        ).upper()

        status_complete = bool(
            betting_status.get("complete")
        )

        players_owing = set(
            betting_status.get("players_owing_action")
            or []
        )

        completed_round = bool(
            status_street == str(phase or "").upper()
            and status_complete
            and not players_owing
        )

        if (
            completed_phase == phase
            and not completed_round
        ):
            emit({
                "type": "hero_fold",
                "street": phase,
            })
            result = (
                f"Hero folded on "
                f"{str(phase).lower()}"
            )

            emit({
                "type": "hand_complete",
                "result": result,
            })

            return fresh_state()

        if completed_round:
            print(
                "[HERO_FOLD_SUPPRESS] "
                f"street={phase} "
                "reason=betting_round_already_complete",
                flush=True,
            )

            # Do not terminate the hand. The board transition may still be
            # awaiting asynchronous confirmation.
            state["hero_clear_seen"] = 0
            return state

        emit({
            "type": "hand_complete",
            "result": "Hero cards cleared / hand ended",
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


def maybe_complete_hand(state, count, frame=None):
    if state.get("phase") != "RIVER":
        # FLOP/TURN board-clear accumulation belongs to maybe_complete_early().
        # Do not reset board_clear_seen here or the early-completion threshold
        # can never be reached.
        state["last_valid_river_frame"] = None
        state["terminal_pot_pending"] = False
        state["terminal_pot_request_id"] = None
        state["terminal_pot_started_ts"] = None
        return state

    # Preserve the newest frame that unquestionably belongs to this hand.
    # A terminal pot read may execute after the board disappears, but it must
    # read pixels captured while the river was still visible.
    if count == 5:
        state["board_clear_seen"] = 0

        if frame is not None:
            state["last_valid_river_frame"] = str(frame)

        return state

    if count == 0:
        state["board_clear_seen"] = (
            state.get("board_clear_seen", 0) + 1
        )
    elif count == 5:
        # A fully visible river disproves an in-progress clear candidate.
        state["board_clear_seen"] = 0
        return state
    else:
        # Once a confirmed five-card river has begun clearing, partial board
        # counts (1-4) are transitional detector noise. Do not let one noisy
        # frame erase accumulated terminal-clear evidence and keep the old hand
        # alive into the next deal.
        return state

    if state["board_clear_seen"] < 4:
        return state

    # First terminal cycle: replace any ordinary in-flight pot request with
    # one tied to the last frame where this river was definitely visible.
    if not state.get("terminal_pot_pending"):
        river_frame_text = state.get("last_valid_river_frame")

        if river_frame_text:
            river_frame = Path(river_frame_text)

            if river_frame.exists():
                state = queue_pot_request(
                    state,
                    river_frame,
                )

                state["terminal_pot_pending"] = True
                state["terminal_pot_request_id"] = (
                    state.get("pot_request_id")
                )
                state["terminal_pot_started_ts"] = time.time()

                print(
                    "[TERMINAL_POT] queued",
                    f"request={str(state.get('pot_request_id') or '')[:8]}",
                    f"frame={river_frame.name}",
                    flush=True,
                )

                return state

        print(
            "[TERMINAL_POT] no valid river frame; completing without final read",
            flush=True,
        )

        emit({
            "type": "hand_complete",
            "result": "Board cleared after river",
        })
        return fresh_state()

    # apply_pot_result() clears pot_request_id after either a successful or
    # failed worker result. Once that happens, settlement is complete and the
    # hand may close. A valid result has already emitted pot_update.
    if state.get("pot_request_id") is None:
        print(
            "[TERMINAL_POT] settled; completing hand",
            flush=True,
        )

        emit({
            "type": "hand_complete",
            "result": "Board cleared after river",
        })
        return fresh_state()

    started = float(
        state.get("terminal_pot_started_ts") or 0.0
    )

    if started and time.time() - started >= 2.5:
        print(
            "[TERMINAL_POT] timeout; completing without final pot result",
            flush=True,
        )

        # Ignore any worker result arriving after the hand is closed.
        state["pot_request_id"] = None
        state["pot_request_ts"] = None

        emit({
            "type": "hand_complete",
            "result": "Board cleared after river",
        })
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
        # If position context exists but this seat is absent from it, the
        # episode belongs to a non-participant / phantom seat. Release it
        # immediately so inference can suppress it instead of allowing it
        # to become a permanent chronology barrier.
        if (
            positions
            and seat != "hero"
            and seat not in positions
        ):
            print(
                "[EPISODE_PHANTOM_RELEASE]",
                f"seat={seat}",
                f"street={street}",
                "reason=seat_not_in_frozen_hand",
                flush=True,
            )
            return True

        # Genuine hand context has not arrived yet. Preserve chronology until
        # position mapping is available.
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
    #
    # Preflop initialization is comparatively noisy, so preserve the full
    # late-stack attachment window there. Postflop, the settled stack reader
    # normally resolves within the 0.45-0.75 second local pipeline window.
    # Do not let one weak visual-only episode block every later chronological
    # action for 2.75 seconds.
    if (
        "bet_region_occupied" in evidence
        and "stack_changed" not in evidence
    ):
        ended_ts = item.get("ended_ts")

        if ended_ts is None:
            return False

        wait_seconds = (
            LATE_STACK_ATTACH_SECONDS
            if street == "PREFLOP"
            else 0.85
        )

        elapsed = (
            time.time() - float(ended_ts)
        )

        # Before the late-stack window expires, hold the episode.
        if elapsed < wait_seconds:
            return False

        # After the window expires, do not allow this weak visual-only
        # episode to block every later episode forever.
        return True

    return True


@dataclass
class CoordinatorRuntime:
    """
    Long-lived objects shared across coordinator perception frames.

    Live mode and deterministic frame replay must use the same instances
    across a hand. Scalar control-flow state remains in main() for now;
    this first refactor changes object ownership only, not behavior.
    """

    local_detector: LocalEventDetector = field(
        default_factory=LocalEventDetector
    )

    hero_blink_buffer: HeroBlinkBuffer = field(
        default_factory=lambda: HeroBlinkBuffer(
            max_samples=6,
            diff_threshold=5.0,
            mean_range_threshold=5.0,
            required_transitions=2,
        )
    )

    sequence_recorder: ActionSequenceRecorder = field(
        default_factory=lambda: ActionSequenceRecorder(
            max_frames=240
        )
    )

    observer: ContinuousObserver = field(
        default_factory=ContinuousObserver
    )

    timeline: ObservationTimeline = field(
        default_factory=ObservationTimeline
    )

    correlator: ObservationCorrelator = field(
        default_factory=ObservationCorrelator
    )

    episode_manager: ActionEpisodeManager = field(
        default_factory=ActionEpisodeManager
    )

    episode_scheduler: StreetEpisodeScheduler = field(
        default_factory=StreetEpisodeScheduler
    )

    inference_engine: ActionInferenceEngine = field(
        default_factory=ActionInferenceEngine
    )

    action_qualifier: ActionQualifier = field(
        default_factory=ActionQualifier
    )

    commitment_tracker: StreetCommitmentTracker = field(
        default_factory=StreetCommitmentTracker
    )

    recent_stack_observations: RecentStackObservations = field(
        default_factory=RecentStackObservations
    )

    participant_frame_buffer: deque = field(
        default_factory=lambda: deque(maxlen=8)
    )

    # Metadata only: no image copies and no OCR on the coordinator hot path.
    # Retains enough recent captures for the asynchronous boundary worker to
    # retrospectively inspect the street that just ended.
    boundary_frame_buffer: deque = field(
        default_factory=lambda: deque(maxlen=32)
    )



def has_semantic_local_change(changes):
    """
    Cheap front-door semantic-frame decision.

    Continuous raw samples still run LocalEventDetector so its
    previous-frame state remains current. Only samples carrying a
    meaningful observable transition enter the expensive coordinator
    pipeline.
    """

    if changes is None:
        return False

    scalar_flags = (
        "hero_changed",
        "board_changed",
        "pot_changed",
        "dealer_changed",
        "action_buttons_changed",
        "hero_cards_appeared",
        "hero_cards_cleared",
    )

    if any(
        bool(getattr(changes, name, False))
        for name in scalar_flags
    ):
        return True

    sequence_flags = (
        "stack_changed_seats",
        "bet_region_appeared",
        "bet_region_cleared",
        "opponent_hole_card_changed_seats",
        "opponent_hole_cards_disappeared_seats",
    )

    if any(
        bool(getattr(changes, name, None))
        for name in sequence_flags
    ):
        return True

    return False


def change_gate_has_pending_work(state):
    """
    Conservative V1 safety gate.

    Never discard a quiet sample while stack settlement is unresolved.
    Other async worker results are consumed before capture at the top of
    the coordinator loop, so they do not require a full quiet-frame pass.
    """

    return bool(
        state.get("pending_stack_reads")
    )


def _timed_stage(timings, name, fn):
    started = time.perf_counter()
    result = fn()
    timings[name] = round(
        (time.perf_counter() - started) * 1000.0,
        3,
    )
    return result


def _append_coordinator_timing(payload):
    COORDINATOR_TIMING.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with COORDINATOR_TIMING.open("a") as handle:
        handle.write(
            json.dumps(
                payload,
                separators=(",", ":"),
                default=str,
            )
            + "\n"
        )
        handle.flush()






def replay_board_semantic_barrier_allows_advance(
    state,
    *,
    next_frame_ts,
):
    """
    Preserve asynchronous board transport ownership without allowing
    board-worker wall time to block recorded perception.

    Canonical board publication remains owned by the outstanding board
    request and is reconciled through the normal worker-result path.
    Local perception, however, must continue at recorded pace just as it
    does during live capture.

    next_frame_ts remains part of this replay contract so callers do not
    need a separate scheduling path.
    """
    return True


def replay_outstanding_transport(state):
    """
    Return durable asynchronous transport that must settle before a replay
    coordinator may exit.

    This intentionally excludes retry inventories such as
    pending_startup_stack_seats and semantic candidates such as
    pending_stack_reads. At replay EOF no new perception is allowed, so only
    requests that were already published to workers are drainable work.
    """
    outstanding = {}

    hero_request_id = state.get("hero_request_id")
    if hero_request_id:
        outstanding["hero"] = [hero_request_id]

    board_request_id = state.get("board_request_id")
    if board_request_id:
        outstanding["board"] = [board_request_id]

    pot_request_id = state.get("pot_request_id")
    if pot_request_id:
        outstanding["pot"] = [pot_request_id]

    bet_requests = dict(
        state.get("pending_bet_amount_requests")
        or {}
    )
    if bet_requests:
        outstanding["bet_amount"] = sorted(
            bet_requests.keys()
        )

    stack_requests = dict(
        state.get("pending_stack_worker_requests")
        or {}
    )
    if stack_requests:
        outstanding["stack"] = sorted(
            stack_requests.keys()
        )

    return outstanding


def replay_drain_complete(state):
    return not replay_outstanding_transport(state)


def replay_pending_stack_candidates(state):
    """
    Return hand-owned settled-stack candidates that still own finite
    prerecorded quantitative work at replay EOF.

    Tokenless/post-hand candidates are not semantic replay obligations.

    pending_stack_worker_requests is the durable transport ledger.
    A candidate-local stack_worker_request_id is only a correlation key.
    If that request no longer exists in durable transport, reconcile the
    stale local key before deciding whether the candidate owns EOF work.
    """
    hand_token = state.get("hand_token")

    if not hand_token:
        return {}

    transport = (
        state.get("pending_stack_worker_requests")
        or {}
    )

    for seat, pending in (
        state.get("pending_stack_reads")
        or {}
    ).items():
        if not isinstance(pending, dict):
            continue

        request_id = pending.get(
            "stack_worker_request_id"
        )

        if (
            request_id
            and request_id not in transport
        ):
            pending.pop(
                "stack_worker_request_id",
                None,
            )

            print(
                "[REPLAY_EOF_STACK_RECONCILE] "
                f"seat={seat} "
                f"request={str(request_id)[:8]} "
                "reason=local_request_absent_from_transport",
                flush=True,
            )

    return {
        seat: dict(pending)
        for seat, pending in (
            state.get("pending_stack_reads")
            or {}
        ).items()
        if (
            isinstance(pending, dict)
            and (
                pending.get("hand_token") in {
                    None,
                    hand_token,
                }
            )
            and not (
                pending.get(
                    "eof_terminal_sample_consumed"
                )
                and not pending.get(
                    "stack_worker_request_id"
                )
            )
        )
    }


def ingest_eof_stack_semantics(
    changes,
    state,
    runtime,
):
    """
    Carry validated replay-EOF stack evidence through the existing
    semantic observer/episode/inference path without performing any
    new perception.

    This helper is replay-EOF only. Live/main-loop behavior remains
    unchanged.
    """
    if changes is None:
        return []

    if not getattr(
        changes,
        "stack_changed_seats",
        None,
    ):
        return []

    if state.get("terminal_action_frozen"):
        return []

    details = (
        getattr(
            changes,
            "stack_change_details",
            {},
        )
        or {}
    )

    origin_streets = {
        str(detail.get("origin_street") or "").upper()
        for detail in details.values()
        if isinstance(detail, dict)
        and detail.get("origin_street")
    }

    # A replay-reconciled quantitative transition owns the street on which
    # its physical candidate originated. Coordinator phase may already have
    # advanced at a board boundary, so phase alone is not authoritative here.
    if len(origin_streets) == 1:
        street = next(iter(origin_streets))
    else:
        street = str(
            state.get("phase")
            or "WAITING"
        ).upper()

    if street == "WAITING":
        return []

    observer = runtime.observer
    timeline = runtime.timeline
    correlator = runtime.correlator
    episode_manager = runtime.episode_manager
    episode_scheduler = runtime.episode_scheduler
    inference_engine = runtime.inference_engine
    action_qualifier = runtime.action_qualifier
    commitment_tracker = runtime.commitment_tracker

    observations = observer.ingest_changes(
        changes,
        street=street,
    )

    if not observations:
        return []

    print(
        "[REPLAY_EOF_SEMANTIC]",
        "stack_changed_seats=",
        list(
            getattr(
                changes,
                "stack_changed_seats",
                [],
            )
            or []
        ),
        "observations=",
        [
            getattr(obs, "type", None)
            for obs in observations
        ],
        flush=True,
    )

    timeline.add_many(observations)
    timeline.write_json(TIMELINE_JSON)

    correlator.ingest(observations)
    CORRELATOR_JSON.write_text(
        json.dumps(
            correlator.summary(),
            indent=2,
        )
    )

    table_context = load_table_context()

    current_commitment_street = street

    table_context[
        "prior_voluntary_commitment_seats"
    ] = commitment_tracker.committed_players(
        current_commitment_street
    )

    # EOF has no new perception frame. Preserve the most recent
    # table context already established by the normal frame path.
    table_context.setdefault(
        "prior_occupied_bet_regions",
        [],
    )

    episode_manager.set_table_context(
        table_context
    )

    episode_manager.ingest(
        observations
    )

    reinference_ids = (
        episode_manager
        .consume_reinference_episode_ids()
    )

    for episode_id in sorted(
        reinference_ids
    ):
        if (
            episode_id
            in inference_engine.suppressed_episode_ids
        ):
            inference_engine.suppressed_episode_ids.discard(
                episode_id
            )

            inference_engine.processed_episode_ids.discard(
                episode_id
            )

            print(
                "[INFERENCE_REOPEN]",
                f"episode={episode_id}",
                "reason=late_stack_after_suppression",
                flush=True,
            )

        elif (
            episode_id
            in inference_engine.processed_episode_ids
        ):
            print(
                "[INFERENCE_REOPEN_SKIP]",
                f"episode={episode_id}",
                "reason=already_published",
                flush=True,
            )

    episode_manager.backfill_table_context(
        table_context
    )

    EPISODES_JSON.write_text(
        json.dumps(
            episode_manager.summary(),
            indent=2,
        )
    )

    released_closed = (
        episode_scheduler.release(
            episode_manager.closed,
            ready_for_inference=(
                episode_ready_for_inference
            ),
            processed_episode_ids=(
                inference_engine
                .processed_episode_ids
            ),
        )
    )

    scheduler_status = (
        episode_scheduler.status(
            episode_manager.closed,
            ready_for_inference=(
                episode_ready_for_inference
            ),
            processed_episode_ids=(
                inference_engine
                .processed_episode_ids
            ),
        )
    )

    EPISODE_SCHEDULER_JSON.write_text(
        json.dumps(
            scheduler_status,
            indent=2,
        )
        + "\n"
    )

    new_actions = (
        inference_engine.ingest_closed(
            released_closed
        )
    )

    published = []

    if new_actions:
        qualified_actions = (
            action_qualifier.qualify_many(
                released_closed,
                new_actions,
            )
        )

        for action, qualification in qualified_actions:

            if (
                qualification is not None
                and not qualification.publish
            ):
                print(
                    "[ACTION_RETIRED]",
                    f"episode={qualification.episode_id}",
                    f"action={qualification.action}",
                    f"reason={qualification.qualification_reason}",
                    flush=True,
                )
                continue

            if (
                action.action
                in {
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

            published.append(action)

            print(
                "[REPLAY_EOF_INFERRED]",
                action.street,
                action.seat,
                action.action,
                f"confidence={action.confidence:.2f}",
                flush=True,
            )

        INFERRED_ACTIONS_JSON.write_text(
            json.dumps(
                inference_engine.to_dict(),
                indent=2,
            )
        )

        ACTION_QUALIFICATIONS_JSON.write_text(
            json.dumps(
                action_qualifier.to_dict(),
                indent=2,
            )
            + "\n"
        )

    return published



def drain_replay_stack_candidates_once(
    state,
    *,
    final_frame_path,
    final_frame_ts,
    replay_records,
):
    """
    Advance deterministic settled-stack work by one non-perception EOF cycle.

    No LocalEventDetector work occurs here. Existing worker results are
    reconciled and the ordinary recorded-time retry logic may publish the next
    prerecorded stack sample. At most one request remains outstanding per
    candidate because process_stack_change_measurements_async() retains its
    existing ownership gate.
    """
    if not replay_pending_stack_candidates(state):
        return state, False, ChangeSet()

    # Deterministic replay owns only finite prerecorded evidence.
    #
    # A settled candidate may already have sampled the newest recorded
    # frame and then schedule an unchanged-stack retry after the recording
    # ends. Recorded semantic time can never reach that deadline.
    #
    # In that exact state there is no additional quantitative evidence
    # available to drain. Preserve the unresolved candidate itself, but
    # mark its one terminal opportunity consumed so it no longer blocks
    # replay completion.
    eof_candidates = (
        state.get("pending_stack_reads")
        or {}
    )

    for seat, entry in eof_candidates.items():
        if not isinstance(entry, dict):
            continue

        if entry.get("stack_worker_request_id"):
            continue

        if entry.get(
            "eof_terminal_sample_consumed"
        ):
            continue

        retry_not_before_ts = entry.get(
            "retry_not_before_ts"
        )

        last_stack_sample_ts = entry.get(
            "last_stack_sample_ts"
        )

        if (
            retry_not_before_ts is None
            or last_stack_sample_ts is None
        ):
            continue

        final_ts = float(final_frame_ts)
        retry_ts = float(retry_not_before_ts)
        sample_ts = float(last_stack_sample_ts)

        last_change_ts = entry.get(
            "last_change_ts"
        )

        # retry_ts - sample_ts is the ordinary semantic
        # settlement interval already carried by this
        # candidate's retry schedule.
        settle_interval = max(
            0.0,
            retry_ts - sample_ts,
        )

        candidate_settled_at_eof = bool(
            last_change_ts is not None
            and (
                final_ts
                - float(last_change_ts)
            )
            >= settle_interval - 1e-9
        )

        # Two finite-recording cases are terminal:
        #
        # 1. The candidate already sampled the final recorded
        #    frame and its next retry lies beyond EOF.
        #
        # 2. The physical candidate is already semantically
        #    settled at EOF, has consumed quantitative evidence,
        #    and its next eligible retry lies beyond EOF.
        #
        # An UNSETTLED physical candidate is deliberately not
        # exhausted here. It retains the existing right to one
        # newest-frame EOF terminal sample.
        if (
            retry_ts > final_ts
            and (
                sample_ts
                >= final_ts - 1e-9
                or candidate_settled_at_eof
            )
        ):
            entry[
                "eof_terminal_sample_consumed"
            ] = True

            print(
                "[REPLAY_EOF_STACK_EXHAUSTED] "
                f"seat={seat} "
                f"last_sample_ts={sample_ts:.6f} "
                f"final_frame_ts={final_ts:.6f} "
                f"retry_not_before_ts={retry_ts:.6f} "
                "reason=no_later_recorded_frame",
                flush=True,
            )

    if not replay_pending_stack_candidates(state):
        save_state(state)
        return state, True, ChangeSet()

    ready = collect_ready_stack_worker_results(
        state,
        replay_frame_ts=float(
            final_frame_ts
        ),
        replay_records=replay_records,
        replay_eof=True,
    )

    settled = {
        seat: item
        for seat, item in ready.items()
        if (
            (item.get("request") or {}).get(
                "purpose"
            )
            == "settled"
        )
    }

    before_requests = set(
        (
            state.get(
                "pending_stack_worker_requests"
            )
            or {}
        ).keys()
    )

    before_candidates = set(
        replay_pending_stack_candidates(
            state
        ).keys()
    )

    changes = ChangeSet()

    # This frame is cycle context only. Retry frame selection remains owned by
    # retry_frame_path/retry_frame_ts derived from replay_records.
    img = cv2.imread(
        str(final_frame_path)
    )

    if img is None:
        raise RuntimeError(
            "replay EOF stack drain requires "
            f"recorded frame: {final_frame_path}"
        )

    if (
        img.shape[1] != 934
        or img.shape[0] != 696
    ):
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    process_stack_change_measurements_async(
        changes,
        img,
        state,
        stack_worker_results=settled,
        prior_occupied_bet_regions=set(),
        prior_commitment_seats=set(),
        event_street=str(
            state.get("phase")
            or "WAITING"
        ).upper(),
        frame_path=str(final_frame_path),
        frame_ts=float(final_frame_ts),
        replay_records=replay_records,
        replay_eof=True,
    )

    after_requests = set(
        (
            state.get(
                "pending_stack_worker_requests"
            )
            or {}
        ).keys()
    )

    after_candidates = set(
        replay_pending_stack_candidates(
            state
        ).keys()
    )

    progressed = bool(
        settled
        or before_requests != after_requests
        or before_candidates != after_candidates
    )

    return state, progressed, changes


def main():
    print("api_event_coordinator running event-only mode. Ctrl+C to stop.")
    print(f"Events: {EVENT_LOG}")
    state = load_state()
    runtime = CoordinatorRuntime()

    local_detector = runtime.local_detector

    # Live mode retains BetRegionStateTracker's monotonic real-time clock.
    #
    # Deterministic replay must use the original recorded frame timeline.
    # PacedReplayCapture intentionally releases overdue frames immediately,
    # so processing wall time cannot be allowed to alter debounce semantics.
    replay = _paced_replay()

    # Recorder-facing tournament-level metadata belongs to main().
    # Initialize it unconditionally so frame recording is safe before
    # Hero-card processing has established any hand-local metadata.
    #
    # Replay metadata is authoritative when present. Live mode refreshes
    # from the current ACR window title on each perception frame below.
    level = (
        dict(replay.tournament_level or {})
        if replay is not None
        else {}
    )

    if replay is not None:
        local_detector.bet_region_tracker.clock = (
            lambda: replay.current_recorded_elapsed
        )

        print(
            "[REPLAY_CLOCK] temporal perception uses "
            "recorded frame time",
            flush=True,
        )

    hero_blink_buffer = runtime.hero_blink_buffer
    previous_blink_visible = False

    sequence_recorder = runtime.sequence_recorder
    record_action_sequence = (
        os.environ.get(
            "POKER_RECORD_ACTION_SEQUENCE"
        )
        == "1"
    )

    if record_action_sequence:
        sequence_dir = sequence_recorder.start_session()
        print(
            f"[DEBUG_SEQUENCE] recording to {sequence_dir}",
            flush=True,
        )
    else:
        print(
            "[DEBUG_SEQUENCE] disabled for live speed "
            "(set POKER_RECORD_ACTION_SEQUENCE=1 to enable)",
            flush=True,
        )

    observer = runtime.observer
    timeline = runtime.timeline
    correlator = runtime.correlator
    episode_manager = runtime.episode_manager
    episode_scheduler = runtime.episode_scheduler
    inference_engine = runtime.inference_engine
    action_qualifier = runtime.action_qualifier

    ACTION_QUALIFICATIONS_JSON.write_text(
        json.dumps(
            action_qualifier.to_dict(),
            indent=2,
        )
        + "\n"
    )

    commitment_tracker = runtime.commitment_tracker
    recent_stack_observations = runtime.recent_stack_observations
    recent_stack_hand_token = None
    commitment_street = "WAITING"
    last_deferred_count = None
    previous_occupied_bet_regions = set()

    # Preserve the captures immediately preceding local Hero-card detection.
    # A fast early-position fold may occur before HAND_START_LOCAL creates the
    # hand token. Replaying this short buffer lets participant evidence retain
    # players who were dealt in but folded before the trigger frame.
    participant_frame_buffer = runtime.participant_frame_buffer
    boundary_frame_buffer = runtime.boundary_frame_buffer


    INFERRED_ACTIONS_JSON.write_text(
        json.dumps(inference_engine.to_dict(), indent=2)
    )

    replay_eof_started = None
    replay_eof_quiet_started = None

    while True:
        # Replay EOF is a transport-drain phase, not another perception frame.
        #
        # PacedReplayCapture deliberately keeps the final frame available after
        # exhaustion so asynchronous work can settle. Do not feed that same
        # frame through LocalEventDetector repeatedly: doing so can create
        # duplicate observations and makes replay completion nondeterministic.
        if replay is not None and replay.exhausted:
            if replay_eof_started is None:
                replay_eof_started = time.monotonic()

                print(
                    "[REPLAY_EOF] final recorded frame released; "
                    "freezing perception and draining transport",
                    flush=True,
                )

            state, consumed_result, _ = (
                consume_ready_worker_results(state)
            )

            # Replay EOF freezes new perception, but deterministic settled-stack
            # candidates may still own finite work against frames that were
            # already recorded. Drain that work without feeding the final frame
            # through LocalEventDetector again.
            stack_candidates = (
                replay_pending_stack_candidates(
                    state
                )
            )

            if stack_candidates:
                final_record = (
                    replay.records[-1]
                    if replay.records
                    else None
                )

                if final_record is not None:
                    state, stack_progressed, eof_stack_changes = (
                        drain_replay_stack_candidates_once(
                            state,
                            final_frame_path=(
                                final_record["frame_path"]
                            ),
                            final_frame_ts=(
                                final_record["ts"]
                            ),
                            replay_records=replay.records,
                        )
                    )

                    if stack_progressed:
                        replay_eof_quiet_started = None

                    if getattr(
                        eof_stack_changes,
                        "stack_changed_seats",
                        None,
                    ):
                        # EOF-produced settled stack evidence must pass
                        # through the same deferred-bet corroboration
                        # contract as ordinary frame-produced evidence.
                        state = release_corroborated_bet_amount_results(
                            state,
                            eof_stack_changes,
                        )

                        ingest_eof_stack_semantics(
                            eof_stack_changes,
                            state,
                            runtime,
                        )

            save_state(state)

            outstanding = replay_outstanding_transport(
                state
            )

            stack_candidates = (
                replay_pending_stack_candidates(
                    state
                )
            )

            if outstanding or stack_candidates:
                replay_eof_quiet_started = None

                print(
                    "[REPLAY_DRAIN] "
                    f"outstanding={outstanding} "
                    f"stack_candidates={sorted(stack_candidates)}",
                    flush=True,
                )

                # Worker results are file-backed and asynchronous. Poll without
                # advancing replay perception or semantic detector time.
                time.sleep(0.02)
                continue

            if replay_eof_quiet_started is None:
                replay_eof_quiet_started = (
                    time.monotonic()
                )

                print(
                    "[REPLAY_DRAIN] transport empty; "
                    "starting quiet period",
                    flush=True,
                )

                time.sleep(0.10)
                continue

            quiet_seconds = (
                time.monotonic()
                - replay_eof_quiet_started
            )

            if quiet_seconds < 0.25:
                time.sleep(0.05)
                continue

            print(
                "[REPLAY_COMPLETE] "
                "transport drained; coordinator exiting cleanly",
                flush=True,
            )

            return

        iteration_started = time.perf_counter()
        frame_timings = {}
        iteration_frame = None

        state, consumed_result, board_emitted_fast = (
            consume_ready_worker_results(state)
        )

        if consumed_result:
            # Let downstream consumers observe emitted worker events before
            # performing another full screen-perception cycle.
            time.sleep(0.01 if not board_emitted_fast else 0.05)
            continue

        # Deterministic replay contract:
        #
        # Before another recorded frame enters LocalEventDetector, reconcile
        # any settled-stack request whose semantic release boundary is reached
        # by that next frame. If the owning worker has not physically finished
        # yet, hold recorded perception at the current frame until it does.
        #
        # Live capture never enters this branch and remains fully asynchronous.
        if (
            replay is not None
            and replay.current_index is not None
            and replay.index < len(replay.records)
        ):
            current_record = replay.records[
                replay.index - 1
            ]
            next_record = replay.records[
                replay.index
            ]

            if not replay_board_semantic_barrier_allows_advance(
                state,
                next_frame_ts=float(
                    next_record["ts"]
                ),
            ):
                # Poll asynchronous board transport without allowing worker
                # wall time to advance recorded perception.
                time.sleep(0.01)
                continue

            replay_stack_gate = (
                reconcile_replay_stack_before_capture(
                    state,
                    current_frame_ts=float(
                        current_record["ts"]
                    ),
                    next_frame_ts=float(
                        next_record["ts"]
                    ),
                    replay_records=replay.records,
                )
            )

            if replay_stack_gate.get("reconciled"):
                semantic_changes = replay_stack_gate.get(
                    "semantic_changes"
                )

                if (
                    semantic_changes is not None
                    and getattr(
                        semantic_changes,
                        "stack_changed_seats",
                        None,
                    )
                ):
                    # This is semantic reconciliation only. Do not create a
                    # synthetic perception frame. Carry the already-validated
                    # quantitative evidence through the same replay-only
                    # observer/episode/inference path used at EOF.
                    state = release_corroborated_bet_amount_results(
                        state,
                        semantic_changes,
                    )

                    ingest_eof_stack_semantics(
                        semantic_changes,
                        state,
                        runtime,
                    )

                save_state(state)

            if not replay_stack_gate.get("advance"):
                # Poll finite asynchronous transport without advancing
                # recorded perception time.
                time.sleep(0.01)
                continue

        capture_started = time.perf_counter()

        use_sck_capture = bool(
            replay is None
            and os.environ.get(
                "POKER_SCK_CAPTURE",
                "0",
            ) == "1"
        )

        if use_sck_capture:
            img, frame = capture_sck_live()
        else:
            frame = capture()
            img = None

        frame_timings["capture"] = round(
            (time.perf_counter() - capture_started) * 1000.0,
            3,
        )

        if replay is not None:
            iteration_frame = replay.current_index

        if use_sck_capture:
            # SCK already supplies the exact canonical 934x696 BGR
            # image. Preserve profiler schema while recording that
            # these stages no longer perform work.
            frame_timings["imread"] = 0.0
            frame_timings["resize"] = 0.0

        else:
            imread_started = time.perf_counter()

            img = (
                cv2.imread(str(frame))
                if frame
                else None
            )

            frame_timings["imread"] = round(
                (
                    time.perf_counter()
                    - imread_started
                )
                * 1000.0,
                3,
            )

            if img is not None:
                resize_started = time.perf_counter()

                img = cv2.resize(
                    img,
                    (934, 696),
                )

                frame_timings["resize"] = round(
                    (
                        time.perf_counter()
                        - resize_started
                    )
                    * 1000.0,
                    3,
                )

        if img is None:
            time.sleep(0.5)
            continue

        participant_frame_buffer.append(
            (
                img.copy(),
                str(frame or ""),
            )
        )

        # Continuously accumulate hand-start participant evidence while
        # the coordinator is already processing live frames. This is
        # intentionally lightweight and independent of API latency.
        participant_started = time.perf_counter()
        collect_participant_evidence(
            img,
            frame,
            state,
        )
        frame_timings["participant_evidence"] = round(
            (time.perf_counter() - participant_started) * 1000.0,
            3,
        )

        prechange_image = (
            local_detector.previous_frame.copy()
            if local_detector.previous_frame is not None
            else None
        )

        detector_started = time.perf_counter()
        changes = local_detector.detect(img)
        frame_timings["local_detector"] = round(
            (time.perf_counter() - detector_started) * 1000.0,
            3,
        )

        # Change-Gated Perception V1.
        #
        # Initially replay-only. Raw sampling and LocalEventDetector still
        # run on EVERY source frame so consecutive-frame transition evidence
        # is preserved. A quiet frame simply does not enter the expensive
        # semantic pipeline unless unresolved stack settlement needs it.
        change_gate_enabled = bool(
            replay is not None
            and os.environ.get(
                "POKER_CHANGE_GATE",
                "0",
            ) == "1"
        )

        semantic_change = has_semantic_local_change(
            changes
        )

        settlement_needed = (
            change_gate_has_pending_work(state)
        )

        if (
            change_gate_enabled
            and str(
                state.get("phase")
                or "WAITING"
            ).upper() != "WAITING"
            and not semantic_change
            and not settlement_needed
        ):
            frame_timings["change_gate"] = 0.0

            _append_coordinator_timing({
                "frame": iteration_frame,
                "street": state.get("phase"),
                "iteration_ms": round(
                    (
                        time.perf_counter()
                        - iteration_started
                    )
                    * 1000.0,
                    3,
                ),
                "stages_ms": frame_timings,
                "acquisition_mode": (
                    "sck"
                    if use_sck_capture
                    else (
                        "replay"
                        if replay is not None
                        else "legacy"
                    )
                ),
                "change_gate": "discarded_quiet",
            })

            continue

        frame_timings["change_gate"] = 1.0

        local_board_count = int(
            getattr(changes, "board_count", 0)
            or 0
        )

        boundary_frame_buffer.append({
            "ts": time.time(),
            "frame_path": str(frame or ""),
            "local_board_count": local_board_count,
        })

        previous_canonical_street = str(
            state.get("phase") or "WAITING"
        ).upper()

        event_street = event_street_for_frame(
            state,
            local_board_count,
        )

        state, _ = maybe_route_acknowledged_boundary(
            state
        )

        old_street_owing_seats = set()

        if event_street != previous_canonical_street:
            # A physical board boundary may remain visible across several
            # frames before canonical old-street chronology is complete.
            #
            # Preserve the last authoritative owing set owned by that exact
            # unresolved boundary. A newer valid state-machine status below
            # refreshes it; a temporarily missing/stale artifact must not
            # erase ownership merely because this is not the first boundary
            # frame.
            boundary_status = load_betting_round_status()

            old_street_owing_seats = (
                refresh_boundary_old_street_owing_seats(
                    state,
                    previous_street=(
                        previous_canonical_street
                    ),
                    next_street=event_street,
                    status=boundary_status,
                )
            )

            authoritative_boundary_status = bool(
                str(
                    (boundary_status or {}).get("hand_token")
                    or ""
                )
                == str(state.get("hand_token") or "")
                and str(
                    (boundary_status or {}).get("street")
                    or ""
                ).upper()
                == previous_canonical_street
            )

            existing_boundary = state.get(
                "pending_boundary_route"
            )

            same_boundary = bool(
                isinstance(existing_boundary, dict)
                and str(
                    existing_boundary.get("hand_token")
                    or ""
                )
                == str(state.get("hand_token") or "")
                and str(
                    existing_boundary.get(
                        "previous_street"
                    )
                    or ""
                ).upper()
                == previous_canonical_street
                and str(
                    existing_boundary.get(
                        "next_street"
                    )
                    or ""
                ).upper()
                == event_street
            )

            if same_boundary:
                existing_boundary[
                    "old_street_owing_seats"
                ] = sorted(
                    old_street_owing_seats
                )

            if not same_boundary:
                state["pending_boundary_route"] = {
                    "hand_token": state.get("hand_token"),
                    "previous_street": (
                        previous_canonical_street
                    ),
                    "next_street": event_street,
                    "frames": list(boundary_frame_buffer),
                    # Preserve the latest authoritative old-street action
                    # ownership across every frame of this unresolved
                    # physical boundary.
                    "old_street_owing_seats": sorted(
                        old_street_owing_seats
                    ),
                    # Set after this frame's ready quantitative evidence
                    # has been reconciled and emitted.
                    "required_event_cursor": None,
                }

                print(
                    "[BOUNDARY_ACK_OPEN] "
                    f"street={previous_canonical_street} "
                    f"next={event_street}",
                    flush=True,
                )

        if event_street != str(
            state.get("phase") or "WAITING"
        ).upper():
            print(
                "[EVENT_STREET] "
                f"canonical={state.get('phase')} "
                f"local_board={getattr(changes, 'board_count', 0)} "
                f"event={event_street}",
                flush=True,
            )

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

            # Replay the short pre-hand capture window. This includes the
            # trigger frame and preceding frames where a fast UTG/SB fold may
            # still have shown both card backs.
            replayed_frames = 0

            for buffered_img, buffered_path in list(
                participant_frame_buffer
            ):
                collect_participant_evidence(
                    buffered_img,
                    buffered_path,
                    state,
                )
                replayed_frames += 1

            print(
                "[PARTICIPANT_PREBUFFER] "
                f"frames={replayed_frames}",
                flush=True,
            )

            state = queue_initial_bet_inventory(
                state,
                img,
                frame,
            )

        current_hand_token = state.get("hand_token")

        if current_hand_token != recent_stack_hand_token:
            recent_stack_observations.clear()
            recent_stack_hand_token = current_hand_token

            print(
                "[STACK_EVIDENCE_RESET] "
                f"hand_token={str(current_hand_token or '')[:8] or 'none'}",
                flush=True,
            )

        current_stack_street = str(
            state.get("phase") or "WAITING"
        ).upper()

        # Chronology is the latency-critical product path.
        #
        # Publish confirmed local actor evidence immediately after local
        # perception and BEFORE startup-stack recovery, settled stack OCR,
        # quantitative action processing, bet sizing, pot work, or any other
        # enrichment. Nothing optional may sit in front of action chronology.
        actor_started = time.perf_counter()
        emit_fast_actor_observations(
            state,
            changes,
            street=event_street,
        )

        emit_physical_actor_completions(
            changes,
            state,
            street=event_street,
        )
        frame_timings["fast_actor"] = round(
            (time.perf_counter() - actor_started) * 1000.0,
            3,
        )

        # Complete ambiguous starting stacks proactively, but only AFTER the
        # chronology fast path above has had the opportunity to publish this
        # frame's physical action evidence.
        startup_started = time.perf_counter()
        state = retry_one_startup_stack(
            state,
            img,
            local_board_count=getattr(
                changes,
                "board_count",
                0,
            ),
        )
        frame_timings["startup_stack_retry"] = round(
            (time.perf_counter() - startup_started) * 1000.0,
            3,
        )

        prior_commitment_seats = (
            commitment_tracker.committed_players(
                current_stack_street
            )
            if current_stack_street != "WAITING"
            else []
        )

        response_to_aggression_seats = set()

        if current_stack_street != "WAITING":
            betting_status = load_betting_round_status()

            for response_seat in (
                betting_status.get(
                    "players_owing_action"
                )
                or []
            ):
                response_context = stack_response_context(
                    betting_status,
                    hand_token=state.get("hand_token"),
                    street=current_stack_street,
                    seat=response_seat,
                )

                if response_context.get(
                    "owes_response"
                ):
                    response_to_aggression_seats.add(
                        response_seat
                    )

            pending_candidate_seats = set(
                (
                    state.get(
                        "pending_stack_reads"
                    )
                    or {}
                ).keys()
            )

            response_to_aggression_seats.update(
                provisional_response_context_seats(
                    state,
                    hand_token=state.get("hand_token"),
                    street=current_stack_street,
                    candidate_seats=pending_candidate_seats,
                )
            )

        if state.get("terminal_action_frozen"):
            # The hand ownership boundary has already been established.
            # Do not allow subsequent table activity to settle into old-hand
            # stack transitions or mutate canonical player stacks.
            #
            # Terminal-pot/result processing remains active independently.
            pending_stack_reads = (
                state.get("pending_stack_reads")
                or {}
            )

            if pending_stack_reads:
                state["pending_stack_reads"] = {}

                print(
                    "[TERMINAL_STACK_QUARANTINE] "
                    f"retired_pending={len(pending_stack_reads)}",
                    flush=True,
                )

            # Strip stack-transition candidates from this frame before the
            # downstream observation/debug pipeline sees them as old-hand
            # player commitments.
            if hasattr(changes, "stack_changed_seats"):
                changes.stack_changed_seats = []

            print(
                "[TERMINAL_STACK_QUARANTINE] "
                "settlement=skipped",
                flush=True,
            )
        else:
            # Collect completed OCR evidence once, immediately before
            # settled-stack reconciliation. Candidate timing, continuity,
            # validation, and action semantics remain unchanged.
            stack_collect_started = time.perf_counter()
            ready_stack_worker_results = (
                collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=(
                        (
                            replay.first_recorded_ts
                            + replay.current_recorded_elapsed
                        )
                        if replay is not None
                        else None
                    ),
                    replay_records=(
                        replay.records
                        if replay is not None
                        else None
                    ),
                )
            )
            frame_timings["stack_result_collect"] = round(
                (
                    time.perf_counter()
                    - stack_collect_started
                )
                * 1000.0,
                3,
            )

            settled_stack_worker_results = {
                seat: item
                for seat, item
                in ready_stack_worker_results.items()
                if (
                    (item.get("request") or {}).get(
                        "purpose"
                    )
                    == "settled"
                )
            }

            stack_reconcile_started = time.perf_counter()
            process_stack_change_measurements_async(
                changes,
                img,
                state,
                stack_worker_results=(
                    settled_stack_worker_results
                ),
                prechange_image=prechange_image,
                prior_occupied_bet_regions=(
                    previous_occupied_bet_regions
                ),
                prior_commitment_seats=prior_commitment_seats,
                response_to_aggression_seats=(
                    response_to_aggression_seats
                ),
                event_street=event_street,
                old_street_owing_seats=old_street_owing_seats,
                recent_stack_observations=recent_stack_observations,
                frame_path=str(frame or ""),
                frame_ts=(
                    (
                        replay.first_recorded_ts
                        + replay.current_recorded_elapsed
                    )
                    if replay is not None
                    else time.time()
                ),
                replay_records=(
                    replay.records
                    if replay is not None
                    else None
                ),
            )
            frame_timings["stack_reconciliation"] = round(
                (
                    time.perf_counter()
                    - stack_reconcile_started
                )
                * 1000.0,
                3,
            )

            state = release_corroborated_bet_amount_results(
                state,
                changes,
            )

            pending_boundary = state.get(
                "pending_boundary_route"
            )

            if (
                isinstance(pending_boundary, dict)
                and pending_boundary.get(
                    "required_event_cursor"
                )
                is None
            ):
                pending_boundary[
                    "required_event_cursor"
                ] = event_log_next_cursor()

                state["pending_boundary_route"] = (
                    pending_boundary
                )

                print(
                    "[BOUNDARY_ACK_ARM] "
                    f"street={pending_boundary.get('previous_street')} "
                    f"next={pending_boundary.get('next_street')} "
                    f"required={pending_boundary.get('required_event_cursor')}",
                    flush=True,
                )

            state, _ = maybe_route_acknowledged_boundary(
                state
            )

            # Stack reconciliation above may have opened or resolved the
            # physical candidate for this exact frame. Freeze that seat-local
            # semantic street now, before bet sizing and observer ingestion.
            state = stamp_bet_region_street_ownership(
                state,
                changes,
                event_street,
                old_street_owing_seats=(
                    old_street_owing_seats
                ),
            )

        log_observation(changes)

        # Absolute visible-bet sizing is asynchronous and never blocks the
        # local Hero/action path. The worker returns numeric evidence only.
        if (
            state.get("phase") != "WAITING"
            and state.get("hand_token")
            and not state.get("terminal_action_frozen")
        ):
            for bet_seat in list(
                getattr(
                    changes,
                    "bet_region_appeared",
                    [],
                )
                or []
            ):
                transition = (
                    (
                        getattr(
                            changes,
                            "bet_region_transitions",
                            {},
                        )
                        or {}
                    ).get(bet_seat)
                    or {}
                )

                bet_street = str(
                    transition.get("origin_street")
                    or event_street
                ).upper()

                state = queue_bet_amount_request(
                    state,
                    frame,
                    bet_seat,
                    bet_street,
                )

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
            forced_pot_baseline_bb = (
                state_machine_state.get(
                    "forced_pot_baseline_bb"
                )
            )

            state = queue_pot_request(
                state,
                frame,
                purpose="initial",
                forced_pot_baseline_bb=(
                    forced_pot_baseline_bb
                ),
            )

            state["initial_pot_queued"] = True

            print(
                "[POT] initial canonical request queued "
                f"forced_baseline={forced_pot_baseline_bb}",
                flush=True,
            )

        if (
            state.get("phase") != "WAITING"
            and not state.get("terminal_pot_pending")
            and bool(getattr(changes, "pot_changed", False))
            and state.get("pot_request_id") is None
        ):
            state = queue_pot_request(state, frame)

        # ------------------------------------------------------------
        # Terminal action-ownership boundary
        # ------------------------------------------------------------
        #
        # WINNER is the strongest local terminal signal. Freeze the old hand
        # immediately and preserve the winning canonical seat. Terminal-pot
        # bookkeeping may continue after this point, but no new betting
        # evidence may become part of this hand.
        #
        # If WINNER was missed, the first local board-clear transition after
        # a confirmed river provides the fallback ownership boundary.
        if (
            state.get("phase") != "WAITING"
            and not state.get("terminal_action_frozen")
        ):
            winner_started = time.perf_counter()
            winner = detect_winner(img)
            frame_timings["winner_detection"] = round(
                (time.perf_counter() - winner_started) * 1000.0,
                3,
            )

            if winner.get("visible"):
                winner_seat = winner.get("seat")

                state["terminal_action_frozen"] = True
                state["terminal_freeze_reason"] = (
                    "winner_detected"
                )
                state["winner_seat"] = winner_seat

                emit({
                    "type": "winner_detected",
                    "seat": winner_seat,
                    "confidence": winner.get(
                        "confidence"
                    ),
                    "score": winner.get("score"),
                    "ts": time.time(),
                })

                print(
                    "[TERMINAL_ACTION_FREEZE] "
                    "reason=winner_detected "
                    f"seat={winner_seat} "
                    f"score={float(winner.get('score') or 0.0):.4f}",
                    flush=True,
                )

            elif (
                str(state.get("phase") or "").upper()
                == "RIVER"
                and int(
                    state.get("confirmed_board_len")
                    or 0
                ) >= 5
                and int(count or 0) == 0
            ):
                state["terminal_action_frozen"] = True
                state["terminal_freeze_reason"] = (
                    "river_board_clear"
                )

                print(
                    "[TERMINAL_ACTION_FREEZE] "
                    "reason=river_board_clear",
                    flush=True,
                )

        observer_pipeline_started = time.perf_counter()

        if replay is None:
            level = parse_tournament_level(
                _CACHED_WINDOW.title
                if _CACHED_WINDOW is not None
                else ""
            )

        sequence_record_started = time.perf_counter()

        if record_action_sequence:
            sequence_recorder.record(
                frame=img,
                changes=changes,
                state=state,
                source_frame=frame,
                tournament_level=level,
            )

        frame_timings["sequence_recorder"] = round(
            (
                time.perf_counter()
                - sequence_record_started
            )
            * 1000.0,
            3,
        )

        print(
            "[CHANGES]",
            "stack_changed_seats=", getattr(changes, "stack_changed_seats", None),
            "bet_region_appeared=", getattr(changes, "bet_region_appeared", None),
            "bet_region_cleared=", getattr(changes, "bet_region_cleared", None),
            flush=True,
        )

        if state.get("terminal_action_frozen"):
            observations = []

            print(
                "[TERMINAL_ACTION_QUARANTINE] "
                f"reason={state.get('terminal_freeze_reason') or 'terminal'} "
                "observations=0",
                flush=True,
            )
        else:
            observations = observer.ingest_changes(
                changes,
                street=event_street,
            )

            owners = state.setdefault(
                "bet_region_street_owners",
                {},
            )

            for cleared_seat in (
                getattr(
                    changes,
                    "bet_region_cleared",
                    [],
                )
                or []
            ):
                owners.pop(
                    cleared_seat,
                    None,
                )

        observer_persist_started = time.perf_counter()

        # Preserve all observer semantics in memory.
        timeline.add_many(observations)
        correlator.ingest(observations)

        # These JSON files are diagnostic artifacts, not inputs to the
        # live action pipeline. Rewriting the entire growing timeline on
        # every frame creates progressively worse real-time latency.
        if os.environ.get(
            "POKER_PERSIST_OBSERVER_DIAGNOSTICS"
        ) == "1":
            timeline.write_json(
                TIMELINE_JSON
            )
            CORRELATOR_JSON.write_text(
                json.dumps(
                    correlator.summary(),
                    indent=2,
                )
            )

        frame_timings["observer_persist"] = round(
            (
                time.perf_counter()
                - observer_persist_started
            )
            * 1000.0,
            3,
        )

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

            reinference_ids = (
                episode_manager.consume_reinference_episode_ids()
            )

            for episode_id in sorted(reinference_ids):
                if (
                    episode_id
                    in inference_engine.suppressed_episode_ids
                ):
                    inference_engine.suppressed_episode_ids.discard(
                        episode_id
                    )
                    inference_engine.processed_episode_ids.discard(
                        episode_id
                    )

                    print(
                        "[INFERENCE_REOPEN]",
                        f"episode={episode_id}",
                        "reason=late_stack_after_suppression",
                        flush=True,
                    )
                elif (
                    episode_id
                    in inference_engine.processed_episode_ids
                ):
                    print(
                        "[INFERENCE_REOPEN_SKIP]",
                        f"episode={episode_id}",
                        "reason=already_published",
                        flush=True,
                    )

            # Diagnostic-only bootstrap analysis.
            #
            # Bet-region occupancy present before the detector baseline cannot
            # produce an "appeared" transition. Once the authoritative
            # preflop positions are available, identify occupied non-blind
            # seats that have not already produced a voluntary commitment.
            if (
                current_commitment_street == "PREFLOP"
                and state_machine_state.get(
                    "canonical_snapshot_ready"
                )
                and not state.get(
                    "bootstrap_occupancy_diagnosed"
                )
            ):
                positions = dict(
                    table_context.get("positions") or {}
                )
                occupied = set(
                    getattr(
                        changes,
                        "occupied_bet_regions",
                        [],
                    )
                    or []
                )
                committed = set(
                    table_context.get(
                        "prior_voluntary_commitment_seats"
                    )
                    or []
                )

                forced = {
                    seat
                    for seat, position in positions.items()
                    if str(position or "").upper()
                    in {"SB", "BB"}
                }

                candidates = sorted(
                    seat
                    for seat in occupied
                    if seat not in forced
                    and seat not in committed
                    and seat in positions
                )

                print(
                    "[BOOTSTRAP_OCCUPANCY] "
                    f"occupied={sorted(occupied)} "
                    f"forced={sorted(forced)} "
                    f"committed={sorted(committed)} "
                    f"candidates={candidates}",
                    flush=True,
                )

                state[
                    "bootstrap_occupancy_diagnosed"
                ] = True

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

            scheduler_status = episode_scheduler.status(
                episode_manager.closed,
                ready_for_inference=episode_ready_for_inference,
                processed_episode_ids=(
                    inference_engine.processed_episode_ids
                ),
            )

            released_closed = episode_scheduler.release(
                episode_manager.closed,
                ready_for_inference=episode_ready_for_inference,
                processed_episode_ids=(
                    inference_engine.processed_episode_ids
                ),
            )

            EPISODE_SCHEDULER_JSON.write_text(
                json.dumps(
                    scheduler_status,
                    indent=2,
                )
                + "\n"
            )

            deferred_count = (
                len(scheduler_status.get("waiting") or [])
                + len(scheduler_status.get("blocked") or [])
            )

            if deferred_count != last_deferred_count:
                if deferred_count:
                    waiting_ids = [
                        item.get("episode_id")
                        for item in (
                            scheduler_status.get("waiting")
                            or []
                        )
                    ]
                    blocked_ids = [
                        item.get("episode_id")
                        for item in (
                            scheduler_status.get("blocked")
                            or []
                        )
                    ]

                    print(
                        "[SCHEDULER] "
                        f"waiting={waiting_ids} "
                        f"blocked={blocked_ids} "
                        "reason=older_episode_barrier",
                        flush=True,
                    )
                elif last_deferred_count:
                    print(
                        "[SCHEDULER] chronology barrier resolved",
                        flush=True,
                    )

                last_deferred_count = deferred_count

            new_actions = inference_engine.ingest_closed(
                released_closed
            )

            if new_actions:
                qualified_actions = (
                    action_qualifier.qualify_many(
                        released_closed,
                        new_actions,
                    )
                )

                for action, qualification in qualified_actions:
                    if qualification is None:
                        print(
                            "[ACTION_QUALIFIER_SKIP]",
                            f"episode={getattr(action, 'episode_id', 0)}",
                            f"action={action.action}",
                            "reason=episode_not_found",
                            flush=True,
                        )
                    else:
                        print(
                            "[ACTION_QUALIFICATION]",
                            f"episode={qualification.episode_id}",
                            f"seat={qualification.seat}",
                            f"street={qualification.street}",
                            f"action={qualification.action}",
                            f"confidence={qualification.confidence:.2f}",
                            f"mature={qualification.evidence_mature}",
                            f"publish={qualification.publish}",
                            f"reason={qualification.qualification_reason}",
                            flush=True,
                        )

                    print(
                        f"[INFERRED] {action.street} {action.seat} "
                        f"{action.action} confidence={action.confidence:.2f}"
                    )

                    if (
                        qualification is not None
                        and not qualification.publish
                    ):
                        print(
                            "[ACTION_RETIRED]",
                            f"episode={qualification.episode_id}",
                            f"action={qualification.action}",
                            f"reason={qualification.qualification_reason}",
                            flush=True,
                        )
                        continue

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

                ACTION_QUALIFICATIONS_JSON.write_text(
                    json.dumps(
                        action_qualifier.to_dict(),
                        indent=2,
                    )
                    + "\n"
                )

        frame_timings["observer_pipeline"] = round(
            (
                time.perf_counter()
                - observer_pipeline_started
            )
            * 1000.0,
            3,
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

        hero_read_started = time.perf_counter()
        state = maybe_read_hero(
            state,
            hero_visible,
            count,
            frame,
        )
        frame_timings["hero_read_coordination"] = round(
            (time.perf_counter() - hero_read_started) * 1000.0,
            3,
        )

        before_board_len = state.get("confirmed_board_len", 0)

        board_started = time.perf_counter()
        state = maybe_read_board(
            state,
            count,
            frame,
            replay_frame_ts=(
                (
                    replay.first_recorded_ts
                    + replay.current_recorded_elapsed
                )
                if replay is not None
                else None
            ),
        )
        frame_timings["board_coordination"] = round(
            (time.perf_counter() - board_started) * 1000.0,
            3,
        )
        board_emitted_this_cycle = state.get("confirmed_board_len", 0) != before_board_len

        # Do not mix a street transition and a Hero turn event in the same
        # observation cycle. Preserve the existing synchronization window so
        # downstream state consumes the board before subsequent action evidence
        # can be attributed to the new street.
        if board_emitted_this_cycle:
            persist_started = time.perf_counter()
            save_state(state)
            frame_timings["state_persist"] = round(
                (time.perf_counter() - persist_started) * 1000.0,
                3,
            )

            _append_coordinator_timing({
                "ts": time.time(),
                "frame": iteration_frame,
                "frame_path": str(frame or ""),
                "street": state.get("phase"),
                "board_count": int(count or 0),
                "iteration_ms": round(
                    (
                        time.perf_counter()
                        - iteration_started
                    )
                    * 1000.0,
                    3,
                ),
                "early_exit": "board_transition",
                "stages_ms": frame_timings,
                "acquisition_mode": (
                    "sck"
                    if use_sck_capture
                    else (
                        "replay"
                        if replay is not None
                        else "legacy"
                    )
                ),
            })

            continue

        # Non-blocking temporal Hero-turn sensor.
        # Reuses the coordinator's existing captured frame.
        blink_visible = False

        blink_started = time.perf_counter()

        if hero_visible:
            # `img` is already the canonical 934x696 frame for this exact
            # observation cycle. Reuse it instead of rereading and resizing
            # the same frame from disk.
            blink_visible = hero_blink_buffer.update(
                img,
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

        frame_timings["hero_blink"] = round(
            (time.perf_counter() - blink_started) * 1000.0,
            3,
        )

        hero_turn_visible = blink_visible or buttons_visible

        # Explicit Hero-card disappearance is stronger action-completion
        # evidence than a trailing nameplate blink. Replay 0001 shows the
        # action buttons disappearing first, Hero cards clearing shortly
        # afterward, and the blink sensor remaining active for another frame.
        #
        # Complete the active decision immediately on the explicit card-clear
        # transition, but leave fold classification to maybe_complete_early()
        # and its existing sustained-clear debounce.
        if (
            changes.hero_cards_cleared
            and state.get("hero_decision_active")
        ):
            emit({"type": "hero_action_complete"})
            state["hero_decision_active"] = False
            state["last_hero_action_complete_phase"] = (
                state.get("phase")
            )

            print(
                "[HERO_ACTION_COMPLETE] "
                f"street={state.get('phase')} "
                "reason=hero_cards_cleared",
                flush=True,
            )
        else:
            state = maybe_emit_hero_decision(
                state,
                hero_turn_visible,
                hero_visible,
            )

        completion_started = time.perf_counter()

        state = maybe_complete_early(
            state,
            count,
            hero_visible,
        )
        state = maybe_complete_hand(
            state,
            count,
            frame=frame,
        )

        frame_timings["hand_completion"] = round(
            (
                time.perf_counter()
                - completion_started
            )
            * 1000.0,
            3,
        )

        persist_started = time.perf_counter()
        save_state(state)
        frame_timings["state_persist"] = round(
            (time.perf_counter() - persist_started) * 1000.0,
            3,
        )

        _append_coordinator_timing({
            "ts": time.time(),
            "frame": iteration_frame,
            "frame_path": str(frame or ""),
            "street": state.get("phase"),
            "board_count": int(count or 0),
            "iteration_ms": round(
                (
                    time.perf_counter()
                    - iteration_started
                )
                * 1000.0,
                3,
            ),
            "early_exit": None,
            "stages_ms": frame_timings,
        })

        # ScreenCaptureKit is already a blocking, frame-paced source.
        #
        # In live SCK mode, immediately return to source.read() after
        # processing this frame. The socket blocks naturally until the next
        # sampled frame arrives, so an additional coordinator sleep only adds
        # avoidable action-detection latency.
        #
        # Preserve the historical polling cadence for replay/legacy capture.
        if not use_sck_capture:
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
