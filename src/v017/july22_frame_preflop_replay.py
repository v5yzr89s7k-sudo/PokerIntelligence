"""
Independent July22 preflop frame replay.

INPUT:
    raw screenshots
    geometry
    initial table facts

FORBIDDEN:
    expected actions
    expected action frames
    july22_complete_hand
    legacy semantic engines

Pixels produce physical observations.
HandEngine alone produces poker semantics.
"""

from pathlib import Path
import json
import time

import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
    count_board_cards,
)
from src.vision.stack_reader import (
    read_stack,
)

from src.v017.hand_engine import (
    HandEngine,
)
from src.v017.stack_motion_gate import (
    measure_stack_motion,
)
from src.v017.fast_stack_resolver import (
    resolve_fast_stack,
)
from src.v017.current_hand_renderer import (
    render_current_hand,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOMETRY = json.loads(
    Path("config/geometry.json").read_text()
)


# Initial table facts only.
PLAYERS = [
    {
        "seat": "seat_upper_right",
        "position": "HJ",
        "name": "Twib101",
        "stack_bb": 106.70,
    },
    {
        "seat": "seat_mid_right",
        "position": "CO",
        "name": "Pablopg",
        "stack_bb": 136.01,
    },
    {
        "seat": "seat_lower_right",
        "position": "BTN",
        "name": "AllinMatt31",
        "stack_bb": 58.55,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "poker5068",
        "stack_bb": 11.78,
    },
    {
        "seat": "seat_lower_left",
        "position": "BB",
        "name": "Birkam",
        "stack_bb": 48.57,
    },
    {
        "seat": "seat_mid_left",
        "position": "UTG",
        "name": "Fartsenia",
        "stack_bb": 17.85,
        "dealt_in": False,
    },
    {
        "seat": "seat_upper_left",
        "position": "LJ",
        "name": "Slayer1950",
        "stack_bb": 59.08,
    },
]


ACTION_ORDER = [
    "seat_upper_left",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
]


TRACKED_STACKS = {
    "seat_lower_right": 58.55,
    "hero": 11.78,
    "seat_lower_left": 48.57,
}


def load_frame(number):
    frame = cv2.imread(
        str(
            ROOT
            / f"{number:04d}_full.png"
        )
    )

    if frame is None:
        raise RuntimeError(
            f"missing frame {number}"
        )

    if frame.shape[:2] != (
        696,
        934,
    ):
        frame = cv2.resize(
            frame,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    return frame


def stack_crop(
    frame,
    seat,
):
    rect = (
        GEOMETRY[
            "stack_regions"
        ][seat]
    )

    return frame[
        int(rect["y"]):
        int(
            rect["y"]
            + rect["height"]
        ),
        int(rect["x"]):
        int(
            rect["x"]
            + rect["width"]
        ),
    ]


def build_engine():
    return HandEngine(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
    )


def replay(
    progression_dir=None,
):
    hand = build_engine()

    trusted_stacks = dict(
        TRACKED_STACKS
    )

    previous_visibility = {}

    # Only seats physically dealt into this hand.
    opponent_seats = [
        "seat_upper_left",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "seat_lower_left",
    ]

    events = []
    publications = []

    previous_frame = None
    previous_text = None

    if progression_dir is not None:
        progression_dir = Path(
            progression_dir
        )

        progression_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    for number in range(
        1,
        53,
    ):
        frame_started = (
            time.perf_counter()
        )

        frame = load_frame(
            number
        )

        board_count = (
            count_board_cards(
                frame,
                GEOMETRY,
            )
        )

        # ----------------------------------------------------
        # Cheap physical card visibility.
        # ----------------------------------------------------

        visibility = {}

        for seat in opponent_seats:
            regions = (
                GEOMETRY[
                    "hole_cards"
                ].get(seat)
            )

            if not regions:
                continue

            visible = bool(
                opponent_cards_visible(
                    frame,
                    regions,
                )
            )

            visibility[seat] = (
                visible
            )

            before = (
                previous_visibility
                .get(seat)
            )

            if (
                before is True
                and visible is False
                and hand.next_actor == seat
            ):
                before_actions = len(
                    hand.actions
                )

                action = (
                    hand
                    .observe_cards_disappeared(
                        seat
                    )
                )

                assert (
                    len(hand.actions)
                    == before_actions + 1
                )

                events.append(
                    {
                        "frame": number,
                        "type":
                            "CARDS_DISAPPEARED",
                        "seat": seat,
                        "semantic_action":
                            action,
                    }
                )

        previous_visibility = (
            visibility
        )

        # ----------------------------------------------------
        # Cheap motion → OCR current actor only.
        #
        # This is crucial: even if some unrelated stack region
        # animates, it cannot create an out-of-order action.
        # ----------------------------------------------------

        if (
            previous_frame is not None
            and hand.next_actor
            in trusted_stacks
        ):
            seat = hand.next_actor

            motion = (
                measure_stack_motion(
                    previous_frame,
                    frame,
                    GEOMETRY,
                    seat,
                )
            )

            if motion.wake:
                prior = (
                    trusted_stacks[
                        seat
                    ]
                )

                ocr_started = (
                    time.perf_counter()
                )

                reading = read_stack(
                    stack_crop(
                        frame,
                        seat,
                    )
                )

                resolution = (
                    resolve_fast_stack(
                        reading,
                        prior,
                    )
                )

                ocr_ms = (
                    time.perf_counter()
                    - ocr_started
                ) * 1000.0

                event = {
                    "frame": number,
                    "type":
                        "STACK_MOTION_WAKE",
                    "seat": seat,
                    "prior": prior,
                    "reader_value":
                        reading.get(
                            "stack_bb"
                        ),
                    "resolved":
                        resolution.resolved,
                    "resolved_value":
                        resolution.value,
                    "ocr_ms":
                        round(
                            ocr_ms,
                            3,
                        ),
                }

                # A wake or unchanged read is not an action.
                if (
                    resolution.resolved
                    and resolution.value
                    is not None
                ):
                    value = float(
                        resolution.value
                    )

                    delta = round(
                        prior - value,
                        2,
                    )

                    if delta > 0.02:
                        action = (
                            hand
                            .observe_stack_commitment(
                                seat,
                                delta,
                            )
                        )

                        trusted_stacks[
                            seat
                        ] = value

                        event[
                            "delta_bb"
                        ] = delta

                        event[
                            "semantic_action"
                        ] = action

                events.append(
                    event
                )

        # ----------------------------------------------------
        # FLOP boundary.
        #
        # For this preflop slice, reaching three board cards
        # proves preflop is over. It may not fabricate any
        # missing quantitative action.
        # ----------------------------------------------------

        if board_count >= 3:
            events.append(
                {
                    "frame": number,
                    "type":
                        "FLOP_BOUNDARY",
                    "next_actor":
                        hand.next_actor,
                }
            )

        # ----------------------------------------------------
        # Product publication.
        # ----------------------------------------------------

        text = render_current_hand(
            hand,
            hand_id=(
                "july22-frame-preflop"
            ),
        )

        if text != previous_text:
            elapsed_ms = (
                time.perf_counter()
                - frame_started
            ) * 1000.0

            publication = {
                "frame": number,
                "action_count":
                    len(hand.actions),
                "next_actor":
                    hand.next_actor,
                "processing_ms":
                    round(
                        elapsed_ms,
                        3,
                    ),
                "text": text,
            }

            publications.append(
                publication
            )

            if progression_dir:
                (
                    progression_dir
                    / (
                        f"frame_{number:04d}"
                        "_current_hand.txt"
                    )
                ).write_text(
                    text
                )

            previous_text = text

        previous_frame = frame

        if board_count >= 3:
            break

    return {
        "hand": hand,
        "events": events,
        "publications":
            publications,
    }
