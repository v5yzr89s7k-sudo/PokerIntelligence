"""
Poker Intelligence v0.17 live observer.

Standalone replacement path:

live ACR frame
    -> FrameHandObserver
    -> HandEngine
    -> authoritative publication
    -> runtime/live/current_hand.txt

Do not run concurrently with the legacy observer.
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import time

import cv2

from src.vision.window_capture import (
    find_acr_table_window,
    capture_window_crop,
)
from src.events.detectors.card_presence import (
    hero_cards_visible,
)
from src.events.detectors.seat_occupancy_detector import (
    occupied_seats,
)
from src.v017.native_seat_occupancy import (
    native_occupied_seats,
)
from src.v017.participant_freeze import (
    ParticipantFreeze,
)
from src.vision.dealer_detector import (
    detect_dealer_button,
)
from src.api.position_engine import (
    assign_positions,
)
from src.bootstrap.hero_bootstrap import (
    bootstrap_local_stacks,
)
from src.api.table_snapshot_reader_core_v2 import read_player_identities_v2
from src.vision.winner_detector import (
    detect_winner,
)

from src.vision.stack_reader import (
    read_stack,
    read_stack_native_fast,
)
from src.api.hero_cards_reader_core import (
    read_hero_cards,
)
from src.api.board_reader_core import (
    read_board,
)
from src.api.pot_api_reader import (
    read_pot,
)
from src.v017.card_observation import (
    normalize_cards,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)

from src.v017.action_order import (
    build_action_order,
    postflop_action_order,
)

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    common_mode_stack_shift_seats,
)
from src.v017.live_product_sink import (
    publish_current_hand_text,
)


ROOT = Path(".")
GEOMETRY = json.loads(
    Path(
        "config/v017/geometry_maximized.json"
    ).read_text()
)

NATIVE_FRAME_SIZE = (
    int(GEOMETRY["table_size"]["width"]),
    int(GEOMETRY["table_size"]["height"]),
)

SENSOR_GEOMETRY = json.loads(
    Path("config/geometry.json").read_text()
)

SENSOR_FRAME_SIZE = (
    int(SENSOR_GEOMETRY["table_size"]["width"]),
    int(SENSOR_GEOMETRY["table_size"]["height"]),
)

CURRENT_HAND = Path(
    "runtime/live/current_hand.txt"
)

LATENCY_TRACE = Path(
    "runtime/live/v017_action_latency.jsonl"
)


def write_latency_trace(record):
    """
    Append diagnostic timing only.

    This function has no perception, semantic, scheduling,
    settlement, or publication authority.
    """
    LATENCY_TRACE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LATENCY_TRACE.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                sort_keys=True,
            )
            + "\n"
        )


BOOTSTRAP_POLL_SECONDS = 0.25
STACK_RETRY_COUNT = 6
STACK_RETRY_SECONDS = 0.30


def crop_geometry_region(
    image,
    region,
):
    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    return image[
        y:y + h,
        x:x + w,
    ]


def capture_image(window):
    path = capture_window_crop(
        window
    )

    image = cv2.imread(
        str(path)
    )

    if image is None:
        raise RuntimeError(
            f"could not read capture {path}"
        )

    native_size = (
        int(image.shape[1]),
        int(image.shape[0]),
    )

    if native_size != NATIVE_FRAME_SIZE:
        raise RuntimeError(
            "v0.17 native frame size mismatch: "
            f"observed={native_size} "
            f"expected={NATIVE_FRAME_SIZE}. "
            "ACR must be maximized at the calibrated size."
        )

    return image, path


def canonical_sensor_frame(
    native_image,
):
    """
    Derive the established 934x696 physical-sensor lane from the
    exact same native capture used by quantitative stack perception.
    """
    width, height = SENSOR_FRAME_SIZE

    return cv2.resize(
        native_image,
        (width, height),
        interpolation=cv2.INTER_AREA,
    )



def player_records(
    seats,
    positions,
    local_players,
    identities=None,
):
    by_seat = {
        row["seat"]: row
        for row in local_players
    }

    identity_by_seat = {
        row.get("seat"): str(
            row.get("name") or ""
        ).strip()
        for row in (identities or [])
        if row.get("seat")
    }

    players = []

    for seat in seats:
        row = by_seat.get(
            seat,
            {}
        )

        stack = row.get(
            "stack_bb"
        )

        players.append(
            {
                "seat": seat,
                "position":
                    positions[seat],
                "name": (
                    identity_by_seat.get(
                        seat
                    )
                    or (
                        "Hero"
                        if seat == "hero"
                        else ""
                    )
                ),
                "stack_bb": (
                    None
                    if stack is None
                    else float(stack)
                ),
                "dealt_in": True,
            }
        )

    return players


def retry_unresolved_stacks(
    window,
    seats,
    local_players,
):
    trusted = {
        row["seat"]: row
        for row in local_players
        if row.get(
            "stack_bb"
        ) is not None
    }

    unresolved = [
        seat
        for seat in seats
        if seat not in trusted
    ]

    for attempt in range(
        1,
        STACK_RETRY_COUNT + 1,
    ):
        if not unresolved:
            break

        time.sleep(
            STACK_RETRY_SECONDS
        )

        image, _ = capture_image(
            window
        )

        retry_rows = (
            bootstrap_local_stacks(
                canonical_image=image,
                frozen_participants=
                    unresolved,
                geometry=GEOMETRY,
                crop_geometry_region=
                    crop_geometry_region,
                stack_reader=read_stack_native_fast,
            )
        )

        for row in retry_rows:
            if (
                row.get("stack_bb")
                is not None
            ):
                trusted[
                    row["seat"]
                ] = row

        unresolved = [
            seat
            for seat in unresolved
            if seat not in trusted
        ]

        print(
            "[BOOTSTRAP_STACK_RETRY]",
            f"attempt={attempt}",
            f"unresolved={unresolved}",
            flush=True,
        )

    ordered = [
        trusted.get(
            seat,
            {
                "seat": seat,
                "stack_bb": None,
            },
        )
        for seat in seats
    ]

    return ordered, unresolved


def wait_for_hand(
    window,
    *,
    clear_confirmed=False,
):
    """
    Acquire the frame that owns Hero identity for one hand.

    Participant topology is frozen from three consecutive identical
    pre-acquisition physical occupancy observations when available.

    Initial startup may attach to cards already visible. In that case
    there may be no historical clean interval, so current-frame
    occupancy remains the explicit fallback.
    """
    print(
        "[BOOTSTRAP] waiting for "
        "Hero cards...",
        f"clear_confirmed={clear_confirmed}",
        flush=True,
    )

    participant_freeze = (
        ParticipantFreeze(
            stable_required=3
        )
    )

    while True:
        image, path = capture_image(
            window
        )

        observed_participants = (
            native_occupied_seats(
                image,
                GEOMETRY,
            )
        )

        frozen = (
            participant_freeze.observe(
                observed_participants
            )
        )

        sensor_image = canonical_sensor_frame(
            image
        )

        if hero_cards_visible(
            sensor_image,
            SENSOR_GEOMETRY,
        ):
            if frozen is None:
                frozen = tuple(
                    observed_participants
                )

                print(
                    "[PARTICIPANT_FREEZE_FALLBACK]",
                    f"seats={frozen}",
                    "reason=hero_visible_before_stable_freeze",
                    flush=True,
                )
            else:
                print(
                    "[PARTICIPANT_FREEZE]",
                    f"seats={frozen}",
                    f"streak={participant_freeze.streak}",
                    flush=True,
                )

            print(
                "[HERO_ACQUISITION]",
                f"frame={Path(path).name}",
                f"clear_confirmed={clear_confirmed}",
                flush=True,
            )

            return (
                image,
                path,
                tuple(frozen),
                participant_freeze.trusted_stacks,
            )

        # Hero visibility was already checked false above.
        # Local stack sampling therefore cannot delay acquisition of
        # a Hero-visible frame.
        stack_rows = bootstrap_local_stacks(
            canonical_image=image,
            frozen_participants=
                observed_participants,
            geometry=GEOMETRY,
            crop_geometry_region=
                crop_geometry_region,
            stack_reader=
                read_stack_native_fast,
        )

        participant_freeze.observe_stack_authority(
            stack_rows,
            frame=Path(path).name,
        )

        time.sleep(
            BOOTSTRAP_POLL_SECONDS
        )


def read_hero_identity(
    frame_path,
):
    result, timing = read_hero_cards(
        frame_path
    )

    raw_cards = (
        result.get("hero_cards")
        or []
    )

    # Local visibility is a wake signal, not identity authority.
    # Empty/malformed API identity must not terminate bootstrap.
    if (
        len(raw_cards) != 2
        or not all(
            isinstance(card, str)
            and card.strip()
            for card in raw_cards
        )
    ):
        print(
            "[BOOTSTRAP_HERO_UNRESOLVED]",
            f"result={result}",
            f"api_ms={timing.get('total_ms')}",
            flush=True,
        )
        return None

    try:
        cards = normalize_cards(
            raw_cards
        )
    except (TypeError, ValueError) as exc:
        print(
            "[BOOTSTRAP_HERO_UNRESOLVED]",
            f"result={result}",
            f"error={exc}",
            flush=True,
        )
        return None

    if (
        len(cards) != 2
        or not all(cards)
    ):
        return None

    print(
        "[BOOTSTRAP_HERO]",
        cards,
        f"api_ms={timing.get('total_ms')}",
        flush=True,
    )

    return cards


def read_board_identity(
    frame_path,
    expected_count,
):
    result, timing = read_board(
        frame_path
    )

    board = normalize_cards(
        result.get("board")
        or result.get("cards")
        or []
    )

    if len(board) < expected_count:
        raise RuntimeError(
            "board identity unresolved: "
            f"expected_at_least={expected_count} "
            f"observed={len(board)} "
            f"result={result}"
        )

    if len(board) not in {
        3,
        4,
        5,
    }:
        raise RuntimeError(
            "board identity invalid length: "
            f"observed={len(board)} "
            f"result={result}"
        )

    print(
        "[BOARD_IDENTITY]",
        board,
        f"requested={expected_count}",
        f"observed={len(board)}",
        f"api_ms={timing.get('total_ms')}",
        flush=True,
    )

    if len(board) > expected_count:
        print(
            "[BOARD_IDENTITY_CATCHUP]",
            f"requested={expected_count}",
            f"observed={len(board)}",
            flush=True,
        )

    return board


def reconcile_board_identity_prefix(
    observer,
    board,
):
    """
    Preserve already accepted canonical board identity.

    A later board observation has authority only over board positions
    that HandEngine has not yet accepted. Previously accepted cards
    are immutable historical state.

    HandEngine.start_street remains the final strict validator.
    """
    observed = list(board)
    canonical = list(
        observer.hand.board
    )

    if len(observed) < len(canonical):
        raise ValueError(
            "board observation shorter than "
            "canonical history: "
            f"canonical={canonical} "
            f"observed={observed}"
        )

    suffix = observed[
        len(canonical):
    ]

    if len(set(suffix)) != len(suffix):
        raise ValueError(
            "new board suffix contains duplicates: "
            f"suffix={suffix}"
        )

    if any(
        card in canonical
        for card in suffix
    ):
        raise ValueError(
            "new board suffix duplicates "
            "canonical history: "
            f"canonical={canonical} "
            f"suffix={suffix}"
        )

    hero_cards = list(
        observer.hand.hero_cards
    )

    if any(
        card in hero_cards
        for card in suffix
    ):
        raise ValueError(
            "new board suffix duplicates Hero card: "
            f"hero_cards={hero_cards} "
            f"suffix={suffix}"
        )

    reconciled = (
        canonical
        + suffix
    )

    if (
        canonical
        and observed[:len(canonical)]
        != canonical
    ):
        print(
            "[BOARD_PREFIX_PRESERVED]",
            f"canonical={canonical}",
            f"observed={observed}",
            f"reconciled={reconciled}",
            flush=True,
        )

    return reconciled


def admit_board_catchup(
    observer,
    *,
    frame_id,
    board,
):
    """
    Admit the newest observed board sequentially.

    A delayed identity read may return a later board than the
    physical boundary that triggered it. Preserve HandEngine
    chronology by decomposing that newer identity into exact
    FLOP -> TURN -> RIVER boundary admissions.

    FrameHandObserver remains strict and receives one exact
    boundary at a time.
    """

    board = list(board)

    contracts = (
        (
            "PREFLOP",
            "FLOP_BOUNDARY_PHYSICAL",
            3,
        ),
        (
            "FLOP",
            "TURN_BOUNDARY_PHYSICAL",
            4,
        ),
        (
            "TURN",
            "RIVER_BOUNDARY_PHYSICAL",
            5,
        ),
    )

    emitted = []

    for (
        current_street,
        boundary_type,
        count,
    ) in contracts:
        if len(board) < count:
            break

        if observer.hand.street != current_street:
            continue

        synthetic_boundary = {
            "frame": frame_id,
            "type": boundary_type,
            "board_count": count,
            "previous_board_count": (
                0
                if count == 3
                else count - 1
            ),
            "proved_by":
                "board_identity_catchup",
        }

        order = postflop_action_order(
            observer
        )

        admitted = observer.admit_street_boundary(
            synthetic_boundary,
            action_order=order,
            board=board[:count],
            complete_pending=True,
        )

        if not admitted:
            print(
                "[BOARD_CATCHUP_BLOCKED]",
                f"frame={frame_id}",
                f"boundary={boundary_type}",
                f"street={observer.hand.street}",
                f"next_actor={observer.hand.next_actor}",
                flush=True,
            )
            break

        emitted.extend(admitted)

        print(
            "[BOARD_CATCHUP_ADMITTED]",
            f"frame={frame_id}",
            f"boundary={boundary_type}",
            f"cards={board[:count]}",
            flush=True,
        )

    return tuple(emitted)


def publish_new(
    observer,
    before_count,
):
    new = observer.publications[
        before_count:
    ]

    completed = []

    for publication in new:
        publish_current_hand_text(
            publication["text"],
            CURRENT_HAND,
        )

        sink_complete_ns = time.perf_counter_ns()

        completed.append(
            {
                "publication": publication,
                "sink_complete_ns": sink_complete_ns,
            }
        )

        print(
            "[PUBLISH]",
            f"frame={publication['frame']}",
            f"street={publication['street']}",
            f"actions={publication['action_count']}",
            flush=True,
        )

    return tuple(completed)



def build_observer_from_frame(
    image,
    frame_path,
    hand_id,
    *,
    frozen_participants=None,
    frozen_stack_authority=None,
):
    """
    Build one V0.17 observer from physical acquisition evidence only.

    This function owns no live-window acquisition and no publication.
    It may therefore be reused by deterministic PNG simulation.
    """
    # The acquisition frame owns one objective starting-pot
    # observation. Run the expensive OCR concurrently with the
    # remaining bootstrap work. It must settle before the initial
    # publication and before any semantic frame transaction.
    pot_executor = ThreadPoolExecutor(
        max_workers=1
    )
    starting_pot_future = (
        pot_executor.submit(
            read_pot,
            frame_path,
        )
    )

    if frozen_participants is None:
        seats = native_occupied_seats(
            image,
            GEOMETRY,
        )
    else:
        seats = list(
            frozen_participants
        )

        print(
            "[BOOTSTRAP_PARTICIPANTS_FROZEN]",
            f"seats={seats}",
            flush=True,
        )

    if "hero" not in seats:
        raise RuntimeError(
            "Hero not present in occupied roster"
        )

    dealer = detect_dealer_button(
        image
    )

    if not dealer.get("found"):
        raise RuntimeError(
            "dealer button unresolved"
        )

    dealer_seat = dealer[
        "dealer_button_seat"
    ]

    positions = assign_positions(
        [
            {"seat": seat}
            for seat in seats
        ],
        dealer_seat,
        preserve_physical_slots=False,
    )

    local_players = (
        bootstrap_local_stacks(
            canonical_image=image,
            frozen_participants=seats,
            geometry=GEOMETRY,
            crop_geometry_region=
                crop_geometry_region,
            stack_reader=read_stack_native_fast,
        )
    )

    # Acquisition-frame stack evidence owns the quantitative baseline.
    #
    # frozen_stack_authority contains observations made strictly before
    # Hero-card acquisition. Those observations remain useful diagnostic
    # evidence, but they cannot be promoted across acquisition because
    # antes/blinds may have changed a player's stack in the meantime.
    #
    # If acquisition-frame OCR is unresolved, leave that seat
    # quantitatively unknown until current/post-acquisition physical
    # evidence establishes a valid baseline.
    frozen_stack_authority = {
        str(seat): float(value)
        for seat, value
        in (
            frozen_stack_authority
            or {}
        ).items()
    }

    if frozen_stack_authority:
        for row in local_players:
            seat = row["seat"]

            if (
                row.get("stack_bb")
                is None
                and seat
                in frozen_stack_authority
            ):
                print(
                    "[BOOTSTRAP_PREACQUISITION_STACK_REJECTED]",
                    f"seat={seat}",
                    "reason=acquisition_frame_unresolved",
                    f"prior_value={frozen_stack_authority[seat]}",
                    flush=True,
                )

    unresolved = [
        row["seat"]
        for row in local_players
        if row.get("stack_bb") is None
    ]

    if unresolved:
        print(
            "[BOOTSTRAP_STACK_UNKNOWN]",
            f"seats={unresolved}",
            "continuing_without_quantitative_authority",
            flush=True,
        )

    hero_cards = read_hero_identity(
        frame_path
    )

    if hero_cards is None:
        print(
            "[BOOTSTRAP_RETRY] "
            "Hero identity unresolved",
            flush=True,
        )
        return None

    identity_snapshot = (
        read_player_identities_v2(
            frame_path,
            dealt_in_seats=seats,
        )
    )

    identities = (
        identity_snapshot.get("players")
        or []
    )

    players = player_records(
        seats,
        positions,
        local_players,
        identities=identities,
    )

    action_order = build_action_order(
        positions
    )

    small_blind = next(
        seat
        for seat, position
        in positions.items()
        if position == "SB"
    )

    big_blind = next(
        seat
        for seat, position
        in positions.items()
        if position == "BB"
    )

    trusted_stacks = {
        row["seat"]:
            float(row["stack_bb"])
        for row in local_players
        if row.get("stack_bb") is not None
    }

    observer = FrameHandObserver(
        players=players,
        action_order=action_order,
        small_blind_seat=small_blind,
        big_blind_seat=big_blind,
        geometry=GEOMETRY,
        trusted_stacks=trusted_stacks,
        opponent_seats=[
            seat
            for seat in seats
            if seat != "hero"
        ],
        quantitative_seats=list(
            trusted_stacks.keys()
        ),
        hero_seat="hero",
        hand_id=str(hand_id),
        stack_reader=read_stack_native_fast,
    )

    observer.hand.observe_hero_cards(
        hero_cards
    )

    try:
        starting_pot_result = (
            starting_pot_future.result()
        )
    finally:
        pot_executor.shutdown(
            wait=True
        )

    if not starting_pot_result.get("ok"):
        raise RuntimeError(
            "starting pot unresolved on acquisition frame: "
            f"{starting_pot_result}"
        )

    starting_pot_bb = (
        starting_pot_result.get("pot_bb")
    )
    starting_pot_support = int(
        starting_pot_result.get("support")
        or 0
    )

    if (
        starting_pot_bb is None
        or starting_pot_support < 2
    ):
        raise RuntimeError(
            "starting pot lacks acquisition authority: "
            f"{starting_pot_result}"
        )

    missing_forced_pot_bb = (
        observer.hand.observe_starting_pot(
            starting_pot_bb
        )
    )

    print(
        "[BOOTSTRAP_STARTING_POT]",
        f"observed={starting_pot_bb}",
        f"support={starting_pot_support}",
        f"missing_forced={missing_forced_pot_bb}",
        f"canonical={observer.hand.pot_bb}",
        flush=True,
    )

    # The acquisition frame is physical baseline evidence, not an
    # action frame. Establish transition sensors without emitting
    # events or granting semantic authority.
    sensor_image = canonical_sensor_frame(
        image
    )

    observer.establish_physical_transition_baseline(
        sensor_image,
        physical_geometry=SENSOR_GEOMETRY,
        native_frame=image,
    )

    observer._publish_if_changed(
        "bootstrap"
    )

    print()
    print(
        "[BOOTSTRAP_COMPLETE]",
        f"players={len(players)}",
        f"dealer={dealer_seat}",
        f"hero_position="
        f"{positions.get('hero')}",
        f"hero_cards={hero_cards}",
        flush=True,
    )

    return observer


def bootstrap_observer(
    window,
    hand_number,
    *,
    clear_confirmed=False,
):
    (
        image,
        frame_path,
        frozen_participants,
        frozen_stack_authority,
    ) = wait_for_hand(
        window,
        clear_confirmed=clear_confirmed,
    )

    observer = build_observer_from_frame(
        image,
        frame_path,
        hand_id=f"live-v017-{hand_number}",
        frozen_participants=
            frozen_participants,
        frozen_stack_authority=
            frozen_stack_authority,
    )

    if observer is None:
        return None

    publish_new(
        observer,
        0,
    )

    return observer


def filter_common_mode_quantitative_events(
    events,
):
    """
    Split one complete physical frame into quantitative observations
    eligible for settlement and correlated common-mode observations
    that must remain evidence-only.

    This function owns no poker semantics and creates no settlement
    ownership.
    """
    quantitative = [
        event
        for event in events
        if event.get("type")
        == "STACK_QUANTITATIVE_OBSERVATION"
    ]

    rejected_seats = common_mode_stack_shift_seats(
        quantitative
    )

    eligible = tuple(
        event
        for event in quantitative
        if event.get("seat") not in rejected_seats
    )

    rejected = tuple(
        event
        for event in quantitative
        if event.get("seat") in rejected_seats
    )

    return eligible, rejected


def retain_frame_card_disappearances(
    observer,
    events,
    *,
    frame_id,
):
    """
    Retain all objective card-disappearance evidence from one physical
    frame before any semantic admission from that frame.

    Raw detector list order must never determine poker chronology.
    """
    retained = []

    for event in events:
        typ = event.get("type")

        if typ not in {
            "OPPONENT_CARDS_DISAPPEARED",
            "HERO_CARDS_DISAPPEARED_PHYSICAL",
        }:
            continue

        observer.retain_card_disappearance(
            event["seat"],
            frame_id=frame_id,
            physical_type=typ,
        )

        retained.append(event)

    return tuple(retained)


def reconcile_frame_evidence(
    observer,
):
    """
    Drain retained evidence after all raw evidence from the current
    physical frame has had its normal authority opportunity.
    """
    card_rows = (
        observer
        .reconcile_pending_card_disappearances()
    )

    quantitative_rows = (
        observer.reconcile_pending_evidence()
    )

    observer.reconcile_pending_card_disappearances()
    observer.reconcile_pending_street_boundaries()

    return (
        tuple(card_rows),
        tuple(quantitative_rows),
    )


class FrameTransactionState:
    """Persistent semantic state for one physical hand."""

    def __init__(self):
        self.settlement_gate = StackSettlementGate()
        self.hero_buttons_active = False
        self.hero_completion_pending_frame = None

        # Diagnostic timing only.
        #
        # Maps physical frame IDs to the capture-completion
        # timestamp of objective evidence first observed there.
        # This state has no semantic authority.
        self.capture_complete_ns_by_frame = {}

        # Diagnostic-only wall clocks for quantitative candidate
        # epochs. These timestamps grant no settlement or semantic
        # authority.
        self.quantitative_first_seen_ns = {}
        self.quantitative_first_seen_frame = {}


class FrameTransactionResult:
    """Observable result of one production frame transaction."""

    def __init__(self, outcome, events):
        self.outcome = str(outcome)
        self.events = tuple(
            dict(event)
            for event in events
        )


def process_frame_transaction(
    observer,
    image,
    frame_path,
    frame_id,
    state,
    *,
    capture_complete_ns=None,
):
    """
    Execute one authoritative physical-frame semantic transaction.

    Live capture and deterministic PNG simulation must use this same
    function. Frame acquisition is deliberately outside this boundary.
    """
    before_publications = len(
        observer.publications
    )

    # Sink cursor may advance within this transaction when an action
    # is deliberately flushed before blocking street-boundary work.
    publication_sink_cursor = before_publications

    before_actions = len(
        observer.hand.actions
    )

    transaction_start_ns = time.perf_counter_ns()

    if capture_complete_ns is None:
        # Deterministic/replay callers do not own live acquisition.
        # Use transaction entry only as a diagnostic fallback.
        capture_complete_ns = transaction_start_ns

    state.capture_complete_ns_by_frame[
        frame_id
    ] = int(capture_complete_ns)

    sensor_image = canonical_sensor_frame(
        image
    )

    result = observer.process_frame(
        image,
        frame_id=frame_id,
        sensor_frame=sensor_image,
        sensor_geometry=SENSOR_GEOMETRY,
    )

    perception_complete_ns = time.perf_counter_ns()

    (
        quantitative_settlement_events,
        common_mode_quantitative_events,
    ) = filter_common_mode_quantitative_events(
        result.events
    )

    common_mode_seats = {
        event.get("seat")
        for event in common_mode_quantitative_events
    }

    frame_card_events = (
        retain_frame_card_disappearances(
            observer,
            result.events,
            frame_id=frame_id,
        )
    )

    hero_cards_disappeared_this_frame = any(
        event.get("type")
        == "HERO_CARDS_DISAPPEARED_PHYSICAL"
        for event in frame_card_events
    )

    boundary_types = {
        "FLOP_BOUNDARY_PHYSICAL",
        "TURN_BOUNDARY_PHYSICAL",
        "RIVER_BOUNDARY_PHYSICAL",
    }

    non_boundary_events = tuple(
        event
        for event in result.events
        if event.get("type")
        not in boundary_types
    )

    boundary_events = tuple(
        event
        for event in result.events
        if event.get("type")
        in boundary_types
    )

    for event in non_boundary_events:
        typ = event["type"]

        if typ in {
            "OPPONENT_CARDS_DISAPPEARED",
            "HERO_CARDS_DISAPPEARED_PHYSICAL",
        }:
            # Already retained before this frame's semantic loop.
            # Preserve Hero physical lifecycle bookkeeping, but
            # defer semantic authority until frame reconciliation.
            if (
                typ
                == "HERO_CARDS_DISAPPEARED_PHYSICAL"
            ):
                state.hero_completion_pending_frame = None
                state.hero_buttons_active = False

            continue

        elif (
            typ
            == "HERO_ACTION_BUTTONS_APPEARED"
        ):
            state.hero_buttons_active = True
            state.hero_completion_pending_frame = None

            print(
                "[HERO_TURN_PHYSICAL]",
                f"frame={frame_id}",
                "buttons=visible",
                f"next_actor={observer.hand.next_actor}",
                flush=True,
            )

        elif (
            typ
            == "HERO_ACTION_BUTTONS_DISAPPEARED"
        ):
            if (
                state.hero_buttons_active
                and observer.hand.next_actor
                == observer.hero_seat
            ):
                state.hero_completion_pending_frame = frame_id

                print(
                    "[HERO_COMPLETION_PENDING]",
                    f"frame={frame_id}",
                    "buttons=disappeared",
                    flush=True,
                )

            state.hero_buttons_active = False

        elif (
            typ
            == "STACK_QUANTITATIVE_OBSERVATION"
        ):
            if event.get("seat") in common_mode_seats:
                print(
                    "[COMMON_MODE_STACK_SHIFT_REJECTED]",
                    f"frame={frame_id}",
                    f"seat={event.get('seat')}",
                    f"prior={event.get('prior')}",
                    f"value={event.get('resolved_value')}",
                    flush=True,
                )
                continue

            # Terminal accounting is a separate authority lane
            # from wager commitment.
            #
            # After authoritative UNCONTESTED completion,
            # HandEngine may expose one exact unmatched commitment.
            # A physical winner-stack increase may confirm that
            # predetermined accounting value. If consumed here,
            # never offer the same observation to wager settlement.
            terminal_rows = (
                observer
                .admit_terminal_stack_return(
                    event
                )
            )

            if terminal_rows:
                for terminal_event in terminal_rows:
                    print(
                        "[TERMINAL_STACK_RETURN]",
                        f"frame={frame_id}",
                        f"seat={terminal_event.get('seat')}",
                        f"prior={terminal_event.get('prior')}",
                        f"value={terminal_event.get('resolved_value')}",
                        f"amount={terminal_event.get('amount_bb')}",
                        flush=True,
                    )

                observer.clear_quantitative_ownership(
                    event.get("seat")
                )
                state.settlement_gate.clear_seat(
                    event.get("seat")
                )

                if (
                    event.get("seat")
                    == observer.hero_seat
                ):
                    state.hero_completion_pending_frame = None
                    state.hero_buttons_active = False

                continue

            # Raw OCR never mutates HandEngine directly.
            #
            # StackSettlementGate requires independent temporal
            # confirmation before a quantitative observation may
            # enter semantic chronology.
            seat = event.get("seat")

            has_commitment_evidence = bool(
                seat
                and seat
                in observer.confirmed_bet_regions
            )

            resolved_value = event.get(
                "resolved_value"
            )

            all_in_confirmed = bool(
                has_commitment_evidence
                and resolved_value is not None
                and abs(
                    float(resolved_value)
                ) <= 0.02
            )

            quantitative_observed_ns = (
                time.perf_counter_ns()
            )

            pending_before = (
                state.settlement_gate.pending.get(
                    str(seat)
                )
                if seat
                else None
            )

            settled = state.settlement_gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=(
                    has_commitment_evidence
                ),
                all_in_confirmed=(
                    all_in_confirmed
                ),
            )

            pending_after = (
                state.settlement_gate.pending.get(
                    str(seat)
                )
                if seat
                else None
            )

            if (
                seat
                and pending_before is None
                and pending_after is not None
            ):
                state.quantitative_first_seen_ns[
                    str(seat)
                ] = quantitative_observed_ns

                state.quantitative_first_seen_frame[
                    str(seat)
                ] = frame_id

                print(
                    "[QUANTITATIVE_CLOCK_ARMED]",
                    f"frame={frame_id}",
                    f"seat={seat}",
                    f"value={event.get('resolved_value')}",
                    flush=True,
                )

            if settled is not None:
                first_seen_ns = (
                    state.quantitative_first_seen_ns.get(
                        str(settled.seat)
                    )
                )

                first_seen_frame = (
                    state.quantitative_first_seen_frame.get(
                        str(settled.seat)
                    )
                )

                if first_seen_ns is not None:
                    print(
                        "[QUANTITATIVE_CLOCK_CONFIRMED]",
                        f"frame={frame_id}",
                        f"seat={settled.seat}",
                        f"first_frame={first_seen_frame}",
                        "first_seen_to_confirmation_ms="
                        f"{(quantitative_observed_ns - first_seen_ns) / 1_000_000.0:.3f}",
                        flush=True,
                    )

            if settled is None:
                print(
                    "[QUANTITATIVE_DEFERRED]",
                    f"frame={frame_id}",
                    f"seat={event.get('seat')}",
                    f"resolved={event.get('resolved')}",
                    f"value={event.get('resolved_value')}",
                    flush=True,
                )
            else:
                # Preserve the original physical observation as
                # semantic input. The gate authorizes it; it does
                # not rewrite its OCR metadata.
                admitted = (
                    observer
                    .admit_quantitative_observation(
                        event
                    )
                )

                if admitted:
                    # Semantic admission consumed this physical
                    # action. Remove only current quantitative
                    # work; future transitions for the same seat
                    # remain eligible normally.
                    observer.clear_quantitative_ownership(
                        settled.seat
                    )
                    state.settlement_gate.clear_seat(
                        settled.seat
                    )

                    state.quantitative_first_seen_ns.pop(
                        str(settled.seat),
                        None,
                    )

                    state.quantitative_first_seen_frame.pop(
                        str(settled.seat),
                        None,
                    )

                if (
                    settled.seat == observer.hero_seat
                    and admitted
                ):
                    state.hero_completion_pending_frame = None
                    state.hero_buttons_active = False

                    print(
                        "[HERO_ACTION_COMPLETE]",
                        f"frame={frame_id}",
                        "source=quantitative",
                        flush=True,
                    )

                print(
                    "[STACK_SETTLED]",
                    f"frame={frame_id}",
                    f"seat={settled.seat}",
                    f"prior={settled.prior}",
                    f"value={settled.value}",
                    f"delta={settled.delta_bb}",
                    f"admitted={len(admitted)}",
                    flush=True,
                )

    # Street-boundary identity is potentially blocking external
    # work. Same-frame non-boundary evidence receives its existing
    # authority opportunity first. Raw detector order does not grant
    # a street boundary semantic priority.
    #
    # If that evidence admitted a canonical action, flush it to the
    # live product before beginning board identity work.
    pre_boundary_publications = ()

    if boundary_events:
        observer._publish_if_changed(
            frame_id
        )

        pre_boundary_publications = publish_new(
            observer,
            publication_sink_cursor,
        )

        publication_sink_cursor = len(
            observer.publications
        )

    for event in boundary_events:
        typ = event["type"]
        expected_count = {
            "FLOP_BOUNDARY_PHYSICAL":
                3,
            "TURN_BOUNDARY_PHYSICAL":
                4,
            "RIVER_BOUNDARY_PHYSICAL":
                5,
        }[typ]

        board_read_start_ns = (
            time.perf_counter_ns()
        )

        actions_before_board_read = len(
            observer.hand.actions
        )

        actions_admitted_before_board = (
            actions_before_board_read
            - before_actions
        )

        publications_flushed_before_board = len(
            pre_boundary_publications
        )

        print(
            "[BOARD_BLOCK_START]",
            f"frame={frame_id}",
            f"type={typ}",
            f"actions_before_tx={before_actions}",
            f"actions_before_board={actions_before_board_read}",
            f"actions_admitted={actions_admitted_before_board}",
            f"publications_flushed={publications_flushed_before_board}",
            flush=True,
        )

        board = read_board_identity(
            frame_path,
            expected_count,
        )

        board_read_end_ns = (
            time.perf_counter_ns()
        )

        board_block_ms = (
            board_read_end_ns
            - board_read_start_ns
        ) / 1_000_000.0

        print(
            "[BOARD_BLOCK_END]",
            f"frame={frame_id}",
            f"type={typ}",
            f"board_ms={board_block_ms:.3f}",
            f"actions_admitted={actions_admitted_before_board}",
            f"publications_flushed={publications_flushed_before_board}",
            flush=True,
        )

        if (
            actions_admitted_before_board > 0
            and publications_flushed_before_board > 0
        ):
            print(
                "[ACTION_PUBLISHED_BEFORE_BOARD]",
                f"frame={frame_id}",
                f"type={typ}",
                f"actions={actions_admitted_before_board}",
                f"board_ms={board_block_ms:.3f}",
                flush=True,
            )

        board = reconcile_board_identity_prefix(
            observer,
            board,
        )

        if len(board) == expected_count:
            # Normal case: preserve ownership of the exact
            # physical boundary that was observed this frame.
            #
            # This is essential when physical board progression
            # outruns semantic chronology. TURN and RIVER must
            # remain independently retained rather than being
            # rewritten as whatever street HandEngine currently
            # expects.
            observer.admit_street_boundary(
                event,
                action_order=postflop_action_order(
                    observer
                ),
                board=board,
                complete_pending=True,
            )
        else:
            # True delayed identity catch-up: the board reader
            # returned a later board than the physical boundary
            # that triggered the read. Sequentially decompose
            # that newer identity through the existing catch-up
            # contract.
            admit_board_catchup(
                observer,
                frame_id=frame_id,
                board=board,
            )


    reconciled_cards, reconciled_quantitative = (
        reconcile_frame_evidence(
            observer
        )
    )

    hero_card_action_reconciled = False

    for reconciled_event in reconciled_cards:
        print(
            "[FRAME_CARD_RECONCILED]",
            f"frame={reconciled_event.get('frame')}",
            f"seat={reconciled_event.get('seat')}",
            f"action={reconciled_event.get('semantic_action')}",
            flush=True,
        )

        if (
            reconciled_event.get("seat")
            == observer.hero_seat
        ):
            hero_card_action_reconciled = True
            state.hero_completion_pending_frame = None
            state.hero_buttons_active = False

            print(
                "[HERO_ACTION_COMPLETE]",
                f"frame={frame_id}",
                f"action={reconciled_event.get('semantic_action')}",
                "source=hero_cards_disappeared",
                flush=True,
            )

    for reconciled_event in reconciled_quantitative:
        print(
            "[FRAME_QUANTITATIVE_RECONCILED]",
            f"frame={reconciled_event.get('frame')}",
            f"seat={reconciled_event.get('seat')}",
            f"action={reconciled_event.get('semantic_action')}",
            flush=True,
        )

    # Frame reconciliation is an authoritative semantic mutation boundary.
    #
    # The low-level reconciliation primitives deliberately own no
    # publication. This transaction does. If retained evidence admitted
    # any semantic action during this frame, immediately project the
    # resulting canonical HandEngine state.
    if (
        reconciled_cards
        or reconciled_quantitative
    ):
        observer._publish_if_changed(
            frame_id
        )

    if (
        hero_cards_disappeared_this_frame
        and not hero_card_action_reconciled
    ):
        # Hero-card disappearance is objective action evidence,
        # not poker-hand termination.
        #
        # If Hero is not yet the authoritative actor, the retained
        # disappearance remains owned by FrameHandObserver until
        # predecessor semantics advance the actor frontier. The hand
        # must continue to be observed after Hero folds.
        print(
            "[HERO_DISAPPEARANCE_RETAINED]",
            f"frame={frame_id}",
            f"next_actor={observer.hand.next_actor}",
            "hand_continues=True",
            flush=True,
        )

    if (
        state.hero_completion_pending_frame is not None
        and frame_id > state.hero_completion_pending_frame
        and observer.hand.next_actor
        == observer.hero_seat
    ):
        hero_player = observer.hand.players[
            observer.hero_seat
        ]

        hero_commitment = float(
            hero_player.street_commitment_bb
        )

        current_price = float(
            observer.hand.current_price_bb
        )

        if abs(
            hero_commitment - current_price
        ) <= 0.02:
            action = (
                observer.hand
                .observe_no_commitment(
                    observer.hero_seat
                )
            )

            state.hero_completion_pending_frame = None

            observer._publish_if_changed(
                frame_id
            )

            print(
                "[HERO_ACTION_COMPLETE]",
                f"frame={frame_id}",
                f"action={action}",
                "source=buttons_no_commitment",
                flush=True,
            )

    winner_result = detect_winner(
        image
    )

    if winner_result.get("visible"):
        terminal_events = (
            observer.admit_terminal_boundary(
                {
                    "frame": frame_id,
                    "type":
                        "WINNER_PHYSICAL",
                    "winner_seat":
                        winner_result.get(
                            "seat"
                        ),
                    "confidence":
                        winner_result.get(
                            "confidence"
                        ),
                    "score":
                        winner_result.get(
                            "score"
                        ),
                    "margin":
                        winner_result.get(
                            "margin"
                        ),
                }
            )
        )

        if terminal_events:
            print(
                "[TERMINAL_WINNER_RECONCILED]",
                f"frame={frame_id}",
                f"winner_seat="
                f"{winner_result.get('seat')}",
                f"events="
                f"{len(terminal_events)}",
                flush=True,
            )

    semantic_complete_ns = time.perf_counter_ns()

    completed_publications = (
        tuple(pre_boundary_publications)
        + tuple(
            publish_new(
                observer,
                publication_sink_cursor,
            )
        )
    )

    after_actions = len(
        observer.hand.actions
    )

    if (
        after_actions > before_actions
        and completed_publications
    ):
        action_rows = observer.hand.actions[
            before_actions:
        ]

        first_publication = completed_publications[0]
        last_publication = completed_publications[-1]

        sink_complete_ns = int(
            last_publication["sink_complete_ns"]
        )

        evidence_frames = [
            event.get("frame")
            for event in result.events
            if event.get("frame") is not None
        ]

        evidence_frame = (
            min(evidence_frames)
            if evidence_frames
            else frame_id
        )

        evidence_capture_ns = (
            state.capture_complete_ns_by_frame.get(
                evidence_frame,
                capture_complete_ns,
            )
        )

        record = {
            "type": "ACTION_LATENCY",
            "transaction_frame": frame_id,
            "evidence_frame": evidence_frame,
            "action_count_before": before_actions,
            "action_count_after": after_actions,
            "actions_added": [
                {
                    "sequence": action.sequence,
                    "street": action.street,
                    "seat": action.seat,
                    "position": action.position,
                    "action": action.action,
                    "amount_bb": action.amount_bb,
                    "raise_to_bb": action.raise_to_bb,
                }
                for action in action_rows
            ],
            "publication_frame": (
                last_publication[
                    "publication"
                ]["frame"]
            ),
            "capture_complete_ns": int(
                evidence_capture_ns
            ),
            "perception_complete_ns": int(
                perception_complete_ns
            ),
            "semantic_complete_ns": int(
                semantic_complete_ns
            ),
            "sink_complete_ns": sink_complete_ns,
            "perception_ms": round(
                (
                    perception_complete_ns
                    - evidence_capture_ns
                )
                / 1_000_000.0,
                3,
            ),
            "semantic_ms": round(
                (
                    semantic_complete_ns
                    - perception_complete_ns
                )
                / 1_000_000.0,
                3,
            ),
            "publish_ms": round(
                (
                    sink_complete_ns
                    - semantic_complete_ns
                )
                / 1_000_000.0,
                3,
            ),
            "end_to_end_ms": round(
                (
                    sink_complete_ns
                    - evidence_capture_ns
                )
                / 1_000_000.0,
                3,
            ),
        }

        write_latency_trace(record)

        print(
            "[ACTION_LATENCY]",
            f"frame={frame_id}",
            f"actions={after_actions - before_actions}",
            f"perception_ms={record['perception_ms']}",
            f"semantic_ms={record['semantic_ms']}",
            f"publish_ms={record['publish_ms']}",
            f"end_to_end_ms={record['end_to_end_ms']}",
            flush=True,
        )

    if observer.hand.hand_complete:
        print(
            "[HAND_COMPLETE]",
            f"actions="
            f"{len(observer.hand.actions)}",
            flush=True,
        )
        return FrameTransactionResult(
            "HAND_COMPLETE",
            result.events,
        )

    return FrameTransactionResult(
        "CONTINUE",
        result.events,
    )


def run_hand(
    window,
    observer,
):
    state = FrameTransactionState()
    frame_id = 0
    prior_capture_complete_ns = None

    while True:
        frame_id += 1

        image, frame_path = (
            capture_image(window)
        )

        capture_complete_ns = time.perf_counter_ns()

        if prior_capture_complete_ns is not None:
            print(
                "[CAPTURE_CADENCE]",
                f"frame={frame_id}",
                "capture_to_capture_ms="
                f"{(capture_complete_ns - prior_capture_complete_ns) / 1_000_000.0:.3f}",
                flush=True,
            )

        prior_capture_complete_ns = (
            capture_complete_ns
        )

        transaction = process_frame_transaction(
            observer,
            image,
            frame_path,
            frame_id,
            state,
            capture_complete_ns=capture_complete_ns,
        )

        if transaction.outcome != "CONTINUE":
            return


def main():
    print(
        "Poker Intelligence v0.17 "
        "LIVE OBSERVER",
        flush=True,
    )

    window = find_acr_table_window()

    if window is None:
        raise RuntimeError(
            "ACR table window not found"
        )

    print(
        "[WINDOW]",
        window.title,
        flush=True,
    )

    hand_number = 0

    while True:
        hand_number += 1

        observer = None

        while observer is None:
            observer = bootstrap_observer(
                window,
                hand_number,
                clear_confirmed=(
                    hand_number > 1
                ),
            )

            if observer is None:
                time.sleep(
                    BOOTSTRAP_POLL_SECONDS
                )

        run_hand(
            window,
            observer,
        )

        print(
            "[NEXT_HAND] waiting...",
            flush=True,
        )

        # Require Hero cards to clear before
        # accepting the next hand.
        while True:
            image, _ = capture_image(
                window
            )

            sensor_image = canonical_sensor_frame(
                image
            )

            if not hero_cards_visible(
                sensor_image,
                SENSOR_GEOMETRY,
            ):
                print(
                    "[HERO_CLEAR_CONFIRMED]",
                    f"after_hand={hand_number}",
                    flush=True,
                )
                break

            time.sleep(
                BOOTSTRAP_POLL_SECONDS
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print(
            "V0.17 live observer stopped."
        )
