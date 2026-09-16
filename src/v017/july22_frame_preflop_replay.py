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
from src.v017.chronology_completion import (
    predecessors_before_actor,
    remaining_before_street_boundary,
)
from src.v017.commitment_normalizer import (
    normalize_commitment_delta,
)
from src.v017.card_observation import (
    board_after_from_transition,
    normalize_cards,
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

BOARD_OBSERVATION_PATH = (
    ROOT
    / "v017_direct_board_transition_reads.json"
)


def load_board_observations():
    if not BOARD_OBSERVATION_PATH.exists():
        raise RuntimeError(
            "missing independent board perception artifact: "
            f"{BOARD_OBSERVATION_PATH}"
        )

    rows = json.loads(
        BOARD_OBSERVATION_PATH.read_text()
    )

    observations = {}

    for row in rows:
        after_frame = int(
            row["after"]
        )

        observation = (
            row.get("observation")
            or {}
        )

        board = (
            board_after_from_transition(
                observation
            )
        )

        hero_cards = normalize_cards(
            observation.get(
                "hero_cards_after"
            )
            or []
        )

        observations[
            after_frame
        ] = {
            "board": board,
            "hero_cards":
                hero_cards,
            "source_before":
                int(row["before"]),
            "source_after":
                after_frame,
        }

    return observations


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

    board_observations = (
        load_board_observations()
    )

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
        116,
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

        if previous_frame is not None:
            # Only physical motion from a seat still present in
            # authoritative chronology may advance semantics.
            #
            # We inspect tracked quantitative seats, but a wake
            # remains merely permission to OCR.
            for seat in (
                "seat_lower_right",
                "hero",
                "seat_lower_left",
            ):
                if seat not in trusted_stacks:
                    continue

                motion = (
                    measure_stack_motion(
                        previous_frame,
                        frame,
                        GEOMETRY,
                        seat,
                    )
                )

                if not motion.wake:
                    continue

                prior = trusted_stacks[
                    seat
                ]

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

                if (
                    resolution.resolved
                    and resolution.value
                    is not None
                ):
                    value = float(
                        resolution.value
                    )

                    physical_delta = round(
                        prior - value,
                        2,
                    )

                    event[
                        "physical_delta_bb"
                    ] = physical_delta

                    if physical_delta > 0.02:
                        # A later physical actor proves all
                        # authoritative predecessors completed first.
                        if (
                            hand.next_actor is not None
                            and seat != hand.next_actor
                            and seat in hand.pending_to_act
                        ):
                            predecessors = (
                                predecessors_before_actor(
                                    hand.pending_to_act,
                                    seat,
                                )
                            )

                            for predecessor in predecessors:
                                action = (
                                    hand.observe_no_commitment(
                                        predecessor
                                    )
                                )

                                events.append(
                                    {
                                        "frame": number,
                                        "type":
                                            "CHRONOLOGY_COMPLETION",
                                        "seat":
                                            predecessor,
                                        "proved_by":
                                            seat,
                                        "semantic_action":
                                            action,
                                    }
                                )

                        # The physical seat must now be authoritative.
                        if hand.next_actor == seat:
                            player = (
                                hand.players[
                                    seat
                                ]
                            )

                            measurement = (
                                normalize_commitment_delta(
                                    observed_delta_bb=(
                                        physical_delta
                                    ),
                                    prior_street_commitment_bb=(
                                        player
                                        .street_commitment_bb
                                    ),
                                    current_price_bb=(
                                        hand
                                        .current_price_bb
                                    ),
                                )
                            )

                            action = (
                                hand.observe_stack_commitment(
                                    seat,
                                    measurement
                                    .normalized_delta_bb,
                                )
                            )

                            trusted_stacks[
                                seat
                            ] = value

                            event[
                                "normalized_delta_bb"
                            ] = (
                                measurement
                                .normalized_delta_bb
                            )

                            event[
                                "snapped_to_call_price"
                            ] = (
                                measurement
                                .snapped_to_call_price
                            )

                            event[
                                "semantic_action"
                            ] = action

                events.append(
                    event
                )

        # ----------------------------------------------------
        # Objective street boundaries.
        # ----------------------------------------------------

        if (
            board_count >= 3
            and hand.street == "PREFLOP"
        ):
            events.append(
                {
                    "frame": number,
                    "type": "FLOP_BOUNDARY",
                    "next_actor_before":
                        hand.next_actor,
                }
            )

            if hand.next_actor is not None:
                raise ValueError(
                    "FLOP appeared before PREFLOP "
                    "chronology closed: "
                    f"next_actor={hand.next_actor}"
                )

            card_observation = (
                board_observations.get(
                    number
                )
            )

            if card_observation is None:
                raise ValueError(
                    "FLOP boundary has no independent "
                    "board identity observation: "
                    f"frame={number}"
                )

            observed_board = list(
                card_observation[
                    "board"
                ]
            )

            if len(observed_board) != 3:
                raise ValueError(
                    "invalid observed FLOP board: "
                    f"{observed_board}"
                )

            observed_hero_cards = list(
                card_observation[
                    "hero_cards"
                ]
            )

            if observed_hero_cards:
                hand.observe_hero_cards(
                    observed_hero_cards
                )

            hand.start_street(
                "FLOP",
                [
                    "hero",
                    "seat_lower_left",
                    "seat_lower_right",
                ],
                board=observed_board,
            )

            events.append(
                {
                    "frame": number,
                    "type":
                        "BOARD_IDENTITY_OBSERVED",
                    "street": "FLOP",
                    "board":
                        observed_board,
                    "hero_cards":
                        observed_hero_cards,
                    "source_frames": [
                        card_observation[
                            "source_before"
                        ],
                        card_observation[
                            "source_after"
                        ],
                    ],
                }
            )

            events.append(
                {
                    "frame": number,
                    "type": "STREET_STARTED",
                    "street": "FLOP",
                    "next_actor":
                        hand.next_actor,
                }
            )

        elif (
            board_count >= 4
            and hand.street == "FLOP"
        ):
            events.append(
                {
                    "frame": number,
                    "type": "TURN_BOUNDARY",
                    "next_actor_before":
                        hand.next_actor,
                }
            )

            if hand.next_actor is not None:
                raise ValueError(
                    "TURN appeared before FLOP "
                    "chronology closed: "
                    f"next_actor={hand.next_actor}"
                )

            card_observation = (
                board_observations.get(
                    number
                )
            )

            if card_observation is None:
                raise ValueError(
                    "TURN boundary has no independent "
                    "board identity observation: "
                    f"frame={number}"
                )

            observed_board = list(
                card_observation[
                    "board"
                ]
            )

            if len(observed_board) != 4:
                raise ValueError(
                    "invalid observed TURN board: "
                    f"{observed_board}"
                )

            if (
                observed_board[:3]
                != list(hand.board)
            ):
                raise ValueError(
                    "TURN board does not extend "
                    "authoritative FLOP board: "
                    f"current={hand.board} "
                    f"observed={observed_board}"
                )

            events.append(
                {
                    "frame": number,
                    "type":
                        "BOARD_IDENTITY_OBSERVED",
                    "street": "TURN",
                    "board":
                        observed_board,
                    "source_frames": [
                        card_observation[
                            "source_before"
                        ],
                        card_observation[
                            "source_after"
                        ],
                    ],
                }
            )

            hand.start_street(
                "TURN",
                [
                    "hero",
                    "seat_lower_left",
                ],
                board=observed_board,
            )

            events.append(
                {
                    "frame": number,
                    "type": "STREET_STARTED",
                    "street": "TURN",
                    "next_actor":
                        hand.next_actor,
                }
            )

        # ----------------------------------------------------
        # RIVER boundary closes remaining TURN chronology.
        # ----------------------------------------------------

        if (
            board_count >= 5
            and hand.street == "TURN"
        ):
            events.append(
                {
                    "frame": number,
                    "type": "RIVER_BOUNDARY",
                    "pending_before":
                        list(
                            hand.pending_to_act
                        ),
                }
            )

            remaining = (
                remaining_before_street_boundary(
                    hand.pending_to_act
                )
            )

            for seat in remaining:
                action = (
                    hand.observe_no_commitment(
                        seat
                    )
                )

                events.append(
                    {
                        "frame": number,
                        "type":
                            "STREET_BOUNDARY_COMPLETION",
                        "street": "TURN",
                        "seat": seat,
                        "proved_by":
                            "RIVER_BOUNDARY",
                        "semantic_action":
                            action,
                    }
                )

            if hand.next_actor is not None:
                raise ValueError(
                    "TURN chronology did not close "
                    "at RIVER boundary: "
                    f"next_actor={hand.next_actor}"
                )

            card_observation = (
                board_observations.get(
                    number
                )
            )

            if card_observation is None:
                raise ValueError(
                    "RIVER boundary has no independent "
                    "board identity observation: "
                    f"frame={number}"
                )

            observed_board = list(
                card_observation[
                    "board"
                ]
            )

            if len(observed_board) != 5:
                raise ValueError(
                    "invalid observed RIVER board: "
                    f"{observed_board}"
                )

            if (
                observed_board[:4]
                != list(hand.board)
            ):
                raise ValueError(
                    "RIVER board does not extend "
                    "authoritative TURN board: "
                    f"current={hand.board} "
                    f"observed={observed_board}"
                )

            events.append(
                {
                    "frame": number,
                    "type":
                        "BOARD_IDENTITY_OBSERVED",
                    "street": "RIVER",
                    "board":
                        observed_board,
                    "source_frames": [
                        card_observation[
                            "source_before"
                        ],
                        card_observation[
                            "source_after"
                        ],
                    ],
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

        if board_count >= 5:
            break

    return {
        "hand": hand,
        "events": events,
        "publications":
            publications,
    }
