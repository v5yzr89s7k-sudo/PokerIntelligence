"""
V0.17 Pixel Lab PNG-only FrameHandObserver runner.

OBSERVER SIDE OF THE ISOLATION WALL.

Allowed inputs:
    * immutable bootstrap table facts;
    * rendered PNG files.

Forbidden:
    * ACR hand parser;
    * ACR truth timeline;
    * ACR pixel renderer;
    * expected actions;
    * expected action frames;
    * generator manifests / truth metadata.

This runner intentionally does not know what actions occurred.
"""

from pathlib import Path
import json

import cv2

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.stack_settlement_gate import (
    StackSettlementGate,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)
from src.api.board_reader_core import (
    read_board,
)
from src.v017.card_observation import (
    normalize_cards,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)

# Immutable acquisition facts only.
#
# Starting stacks are presentation/table-start facts.
# trusted_stacks below are the physical post-forced-contribution
# acquisition state visible in the first observer PNG.
PLAYERS = [
    {
        "seat": "seat_mid_right",
        "position": "UTG",
        "name": "FERITIN",
        "stack_bb": 103.98,
        "dealt_in": True,
    },
    {
        "seat": "seat_lower_right",
        "position": "HJ",
        "name": "Dayzdnconfused",
        "stack_bb": 99.76,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "CO",
        "name": "poker5068",
        "stack_bb": 99.88,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "seat_upper_left",
        "position": "BTN",
        "name": "Gfr0g",
        "stack_bb": 132.02,
        "dealt_in": True,
    },
    {
        "seat": "seat_top",
        "position": "SB",
        "name": "STRAIGHTKK",
        "stack_bb": 69.84,
        "dealt_in": True,
    },
    {
        "seat": "seat_upper_right",
        "position": "BB",
        "name": "vassagoOG",
        "stack_bb": 97.76,
        "dealt_in": True,
    },
]

ACTION_ORDER = [
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_upper_left",
    "seat_top",
    "seat_upper_right",
]

TRUSTED_STACKS = {
    "seat_mid_right": 103.86,
    "seat_lower_right": 99.64,
    "hero": 99.76,
    "seat_upper_left": 131.90,
    "seat_top": 69.22,
    "seat_upper_right": 96.64,
}

OPPONENT_SEATS = [
    "seat_mid_right",
    "seat_lower_right",
    "seat_upper_left",
    "seat_top",
    "seat_upper_right",
]


def read_board_from_png(
    path,
    *,
    expected_count,
):
    """
    Observer-side board identity from PNG pixels only.

    No generator metadata or ACR truth enters this function.
    """
    result, timing = read_board(
        path,
        image_mode="both",
    )

    cards = normalize_cards(
        result.get("board")
        or result.get("cards")
        or []
    )

    if len(cards) < expected_count:
        raise RuntimeError(
            "board identity unresolved from PNG: "
            f"path={path} "
            f"expected={expected_count} "
            f"observed={cards} "
            f"result={result}"
        )

    cards = cards[:expected_count]

    print(
        "[PIXEL_BOARD_IDENTITY]",
        f"frame={path.name}",
        f"cards={cards}",
        f"confidence={result.get('confidence')}",
        f"api_ms={timing.get('api_ms')}",
        flush=True,
    )

    return cards


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="seat_top",
        big_blind_seat="seat_upper_right",
        geometry=GEOMETRY,
        trusted_stacks=dict(
            TRUSTED_STACKS
        ),
        opponent_seats=list(
            OPPONENT_SEATS
        ),
        quantitative_seats=list(
            TRUSTED_STACKS
        ),
        hero_seat="hero",
        hand_id="pixel-real-acr-2826874674",
        stack_reader=read_stack_native_fast,
    )


def run():
    paths = tuple(
        sorted(
            OBSERVER_INPUT.glob(
                "frame_*.png"
            )
        )
    )

    if not paths:
        raise RuntimeError(
            f"no observer PNGs: {OBSERVER_INPUT}"
        )

    observer = build_observer()
    gate = StackSettlementGate()

    physical_events = []
    admitted = []
    boundaries = []

    print(
        "===== PNG-ONLY FRAMEHANDOBSERVER ====="
    )
    print(
        "input frames =",
        tuple(
            path.name
            for path in paths
        ),
    )
    print(
        "initial next_actor =",
        observer.hand.next_actor,
    )
    print(
        "initial trusted_stacks =",
        observer.trusted_stacks,
    )

    for path in paths:
        frame_id = int(
            path.stem.split("_")[-1]
        )

        image = cv2.imread(str(path))
        assert image is not None, path

        result = observer.process_frame(
            image,
            frame_id=frame_id,
        )

        if result.events:
            print()
            print(
                "FRAME",
                frame_id,
            )

        # --------------------------------------------------------
        # FRAME-BATCH CARD OWNERSHIP
        # --------------------------------------------------------
        #
        # Card disappearance and quantitative evidence may become
        # visible in the same physical frame.
        #
        # Raw detector list order must not decide poker chronology.
        # Preserve every disappearance first. Quantitative evidence
        # then gets its normal chronology-completion opportunity.
        # Finally, retained card evidence is reconciled against the
        # resulting authoritative frontier.
        frame_card_events = [
            event
            for event in result.events
            if event.get("type") in {
                "OPPONENT_CARDS_DISAPPEARED",
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
            }
        ]

        for event in frame_card_events:
            observer._retain_pending_card_disappearance(
                event["seat"],
                frame_id=frame_id,
                physical_type=event["type"],
            )

        for event in result.events:
            row = dict(event)
            physical_events.append(row)

            print(
                " physical",
                row,
            )

            typ = event.get("type")

            if typ in {
                "OPPONENT_CARDS_DISAPPEARED",
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
            }:
                # Already retained above. Semantic admission waits until
                # all other evidence from this physical frame has had
                # its chronology opportunity.
                continue

            if typ in {
                "FLOP_BOUNDARY_PHYSICAL",
                "TURN_BOUNDARY_PHYSICAL",
                "RIVER_BOUNDARY_PHYSICAL",
            }:
                board_count = int(
                    event["board_count"]
                )

                boundaries.append(
                    (
                        frame_id,
                        typ,
                        event.get(
                            "previous_board_count"
                        ),
                        board_count,
                    )
                )

                board = read_board_from_png(
                    path,
                    expected_count=board_count,
                )

                # Postflop order is derived solely from bootstrap
                # positions plus the observer's own folded state.
                #
                # Heads-up here is BB then Hero/CO.
                postflop_order = [
                    seat
                    for seat in (
                        "seat_top",
                        "seat_upper_right",
                        "seat_mid_right",
                        "seat_lower_right",
                        "hero",
                        "seat_upper_left",
                    )
                    if (
                        seat in observer.hand.players
                        and not observer.hand.players[
                            seat
                        ].folded
                    )
                ]

                rows = observer.admit_street_boundary(
                    event,
                    action_order=postflop_order,
                    board=board,
                )

                for admitted_event in rows:
                    admitted.append(
                        (
                            frame_id,
                            admitted_event.get(
                                "seat"
                            ),
                            admitted_event.get(
                                "semantic_action"
                            ),
                            "street_boundary",
                        )
                    )

                    print(
                        " admitted",
                        admitted[-1],
                    )

                continue

            if typ != "STACK_QUANTITATIVE_OBSERVATION":
                continue

            # Terminal accounting is a separate semantic lane from
            # wager commitment. The ordinary quantitative resolver
            # correctly rejects stack increases; after authoritative
            # UNCONTESTED completion, however, HandEngine may expose
            # one exact permissible uncalled-return value.
            terminal_rows = (
                observer
                .admit_terminal_stack_return(
                    event
                )
            )

            if terminal_rows:
                for terminal_event in terminal_rows:
                    admitted.append(
                        (
                            frame_id,
                            terminal_event.get(
                                "seat"
                            ),
                            "UNCALLED_RETURN",
                            "terminal_accounting",
                        )
                    )

                    print(
                        " admitted",
                        admitted[-1],
                    )

                # The physical observation has been consumed by the
                # terminal accounting lane. Never offer the same stack
                # increase to wager settlement.
                continue

            settled = gate.observe(
                event,
                phase=observer.hand.street,
                has_commitment_evidence=False,
                all_in_confirmed=False,
            )

            if settled is None:
                continue

            rows = (
                observer
                .admit_quantitative_observation(
                    event
                )
            )

            if rows:
                for admitted_event in rows:
                    admitted.append(
                        (
                            frame_id,
                            admitted_event.get(
                                "seat"
                            ),
                            admitted_event.get(
                                "semantic_action"
                            ),
                            "quantitative",
                        )
                    )

                    print(
                        " admitted",
                        admitted[-1],
                    )

                observer.clear_quantitative_ownership(
                    settled.seat
                )
                gate.clear_seat(
                    settled.seat
                )

        # All physical evidence from this frame has now had its
        # opportunity. Consume retained card disappearances only when
        # their seat is authoritative under the resulting chronology.
        reconciled_cards = (
            observer
            .reconcile_pending_card_disappearances()
        )

        for reconciled_event in reconciled_cards:
            admitted.append(
                (
                    reconciled_event.get("frame"),
                    reconciled_event.get("seat"),
                    reconciled_event.get(
                        "semantic_action"
                    ),
                    "card_disappearance_reconciled",
                )
            )

            print(
                " admitted",
                admitted[-1],
            )

        # Card reconciliation may itself close a betting obligation and
        # expose previously retained quantitative/street evidence.
        reconciled_quantitative = (
            observer.reconcile_pending_evidence()
        )

        if reconciled_quantitative:
            for reconciled_event in (
                reconciled_quantitative
            ):
                admitted.append(
                    (
                        reconciled_event.get("frame"),
                        reconciled_event.get("seat"),
                        reconciled_event.get(
                            "semantic_action"
                        ),
                        "quantitative_reconciled",
                    )
                )

                print(
                    " admitted",
                    admitted[-1],
                )

        observer.reconcile_pending_card_disappearances()
        observer.reconcile_pending_street_boundaries()

    print()
    print("===== OBSERVED HANDENGINE ACTIONS =====")

    actions = tuple(
        (
            action.sequence,
            action.street,
            action.seat,
            action.position,
            action.name,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in observer.hand.actions
    )

    for row in actions:
        print(row)

    print()
    print("===== PHYSICAL STREET BOUNDARIES =====")
    for row in boundaries:
        print(row)

    print()
    print("===== FINAL OBSERVER STATE =====")
    print(
        "street =",
        observer.hand.street,
    )
    print(
        "next_actor =",
        observer.hand.next_actor,
    )
    print(
        "trusted_stacks =",
        observer.trusted_stacks,
    )
    print(
        "pending_quantitative =",
        observer.pending_quantitative_evidence,
    )
    print(
        "pending_card_disappearances =",
        observer.pending_card_disappearances,
    )

    return {
        "observer": observer,
        "physical_events": tuple(
            physical_events
        ),
        "admitted": tuple(admitted),
        "boundaries": tuple(boundaries),
        "actions": actions,
    }


if __name__ == "__main__":
    run()
