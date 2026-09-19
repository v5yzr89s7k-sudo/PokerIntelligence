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
from src.vision.dealer_detector import (
    detect_dealer_button,
)
from src.api.position_engine import (
    assign_positions,
)
from src.bootstrap.hero_bootstrap import (
    bootstrap_local_stacks,
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
from src.v017.card_observation import (
    normalize_cards,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
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

FRAME_INTERVAL_SECONDS = 0.20
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


def build_action_order(
    positions,
):
    preflop_order = [
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
        "BTN",
        "SB",
        "BB",
    ]

    rank = {
        position: index
        for index, position
        in enumerate(preflop_order)
    }

    return sorted(
        positions,
        key=lambda seat: (
            rank.get(
                positions.get(seat),
                999,
            ),
            seat,
        ),
    )


def postflop_action_order(
    observer,
):
    position_order = [
        "SB",
        "BB",
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
        "BTN",
    ]

    rank = {
        position: index
        for index, position
        in enumerate(position_order)
    }

    seats = [
        seat
        for seat, player
        in observer.hand.players.items()
        if (
            player.dealt_in
            and not player.folded
        )
    ]

    return sorted(
        seats,
        key=lambda seat: (
            rank.get(
                observer.hand.players[
                    seat
                ].position,
                999,
            ),
            seat,
        ),
    )


def player_records(
    seats,
    positions,
    local_players,
):
    by_seat = {
        row["seat"]: row
        for row in local_players
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
                    "Hero"
                    if seat == "hero"
                    else seat
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

    Initial startup may attach to cards already visible.

    Every subsequent hand must be preceded by an explicit canonical
    Hero-card clear observed by main(). clear_confirmed is therefore
    an ownership fact, not a card-identity comparison.
    """
    print(
        "[BOOTSTRAP] waiting for "
        "Hero cards...",
        f"clear_confirmed={clear_confirmed}",
        flush=True,
    )

    while True:
        image, path = capture_image(
            window
        )

        sensor_image = canonical_sensor_frame(
            image
        )

        if hero_cards_visible(
            sensor_image,
            SENSOR_GEOMETRY,
        ):
            print(
                "[HERO_ACQUISITION]",
                f"frame={Path(path).name}",
                f"clear_confirmed={clear_confirmed}",
                flush=True,
            )
            return image, path

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

    for publication in new:
        publish_current_hand_text(
            publication["text"],
            CURRENT_HAND,
        )

        print(
            "[PUBLISH]",
            f"frame={publication['frame']}",
            f"street={publication['street']}",
            f"actions={publication['action_count']}",
            flush=True,
        )


def bootstrap_observer(
    window,
    hand_number,
    *,
    clear_confirmed=False,
):
    image, frame_path = (
        wait_for_hand(
            window,
            clear_confirmed=clear_confirmed,
        )
    )

    seats = native_occupied_seats(
        image,
        GEOMETRY,
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

    players = player_records(
        seats,
        positions,
        local_players,
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
        trusted_stacks=
            trusted_stacks,
        opponent_seats=[
            seat
            for seat in seats
            if seat != "hero"
        ],
        quantitative_seats=
            list(
                trusted_stacks.keys()
            ),
        hero_seat="hero",
        hand_id=(
            f"live-v017-{hand_number}"
        ),
        stack_reader=read_stack_native_fast,
    )

    observer.hand.observe_hero_cards(
        hero_cards
    )

    # Publish initial authoritative hand,
    # including forced blinds and Hero cards.
    observer._publish_if_changed(
        "bootstrap"
    )

    publish_new(
        observer,
        0,
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


def run_hand(
    window,
    observer,
):
    # Settlement ownership is per physical hand.
    # Pending quantitative evidence must never cross a hand boundary.
    settlement_gate = StackSettlementGate()

    # Physical Hero action lifecycle.
    #
    # Button disappearance is completion evidence, not immediate
    # CHECK authority. Give quantitative/card evidence a later
    # frame to resolve CALL/RAISE/FOLD first.
    hero_buttons_active = False
    hero_completion_pending_frame = None

    frame_id = 0

    while True:
        frame_id += 1

        image, frame_path = (
            capture_image(window)
        )

        before_publications = len(
            observer.publications
        )

        sensor_image = canonical_sensor_frame(
            image
        )

        result = observer.process_frame(
            image,
            frame_id=frame_id,
            sensor_frame=sensor_image,
            sensor_geometry=SENSOR_GEOMETRY,
        )

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

        for event in result.events:
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
                    hero_completion_pending_frame = None
                    hero_buttons_active = False

                continue

            elif (
                typ
                == "HERO_ACTION_BUTTONS_APPEARED"
            ):
                hero_buttons_active = True
                hero_completion_pending_frame = None

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
                    hero_buttons_active
                    and observer.hand.next_actor
                    == observer.hero_seat
                ):
                    hero_completion_pending_frame = frame_id

                    print(
                        "[HERO_COMPLETION_PENDING]",
                        f"frame={frame_id}",
                        "buttons=disappeared",
                        flush=True,
                    )

                hero_buttons_active = False

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

                settled = settlement_gate.observe(
                    event,
                    phase=observer.hand.street,
                    has_commitment_evidence=(
                        has_commitment_evidence
                    ),
                    all_in_confirmed=(
                        all_in_confirmed
                    ),
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
                        settlement_gate.clear_seat(
                            settled.seat
                        )

                    if (
                        settled.seat == observer.hero_seat
                        and admitted
                    ):
                        hero_completion_pending_frame = None
                        hero_buttons_active = False

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

            elif typ in {
                "FLOP_BOUNDARY_PHYSICAL",
                "TURN_BOUNDARY_PHYSICAL",
                "RIVER_BOUNDARY_PHYSICAL",
            }:
                expected_count = {
                    "FLOP_BOUNDARY_PHYSICAL":
                        3,
                    "TURN_BOUNDARY_PHYSICAL":
                        4,
                    "RIVER_BOUNDARY_PHYSICAL":
                        5,
                }[typ]

                board = read_board_identity(
                    frame_path,
                    expected_count,
                )

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
                hero_completion_pending_frame = None
                hero_buttons_active = False

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

        if (
            hero_cards_disappeared_this_frame
            and not hero_card_action_reconciled
        ):
            publish_new(
                observer,
                before_publications,
            )

            print(
                "[PHYSICAL_HAND_END]",
                f"frame={frame_id}",
                "reason=hero_cards_disappeared",
                "after=frame_reconciliation",
                flush=True,
            )

            return

        if (
            hero_completion_pending_frame is not None
            and frame_id > hero_completion_pending_frame
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

                hero_completion_pending_frame = None

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

        publish_new(
            observer,
            before_publications,
        )

        if (
            observer.hand.street
            == "RIVER"
            and observer.hand.next_actor
            is None
        ):
            print(
                "[HAND_COMPLETE]",
                f"actions="
                f"{len(observer.hand.actions)}",
                flush=True,
            )
            return

        time.sleep(
            FRAME_INTERVAL_SECONDS
        )


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
