"""
G3.5A contract.

FrameHandObserver detects objective physical board/street boundaries
without mutating authoritative HandEngine poker semantics.
"""

from unittest.mock import patch

import numpy as np

from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 20.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 20.0,
    },
]


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="g3.5a-contract",
    )


def boundary_events(result):
    return [
        event
        for event in result.events
        if event["type"].endswith(
            "_BOUNDARY_PHYSICAL"
        )
    ]


def main():
    observer = build_observer()

    frame = np.zeros(
        (20, 20, 3),
        dtype=np.uint8,
    )

    initial_street = observer.hand.street
    initial_actions = list(
        observer.hand.actions
    )
    initial_next_actor = observer.hand.next_actor

    # Stable frames must not duplicate boundaries.
    counts = [
        0,
        0,
        3,
        3,
        4,
        4,
        5,
        5,
    ]

    emitted = []

    with patch(
        "src.v017.frame_hand_observer.count_board_cards",
        side_effect=counts,
    ), patch(
        "src.v017.frame_hand_observer.hero_cards_visible",
        return_value=False,
    ):
        for frame_id in range(
            1,
            len(counts) + 1,
        ):
            result = observer.process_frame(
                frame.copy(),
                frame_id=frame_id,
            )
            emitted.extend(
                boundary_events(result)
            )

    assert [
        event["type"]
        for event in emitted
    ] == [
        "FLOP_BOUNDARY_PHYSICAL",
        "TURN_BOUNDARY_PHYSICAL",
        "RIVER_BOUNDARY_PHYSICAL",
    ], emitted

    assert [
        event["frame"]
        for event in emitted
    ] == [
        3,
        5,
        7,
    ], emitted

    assert [
        event["board_count"]
        for event in emitted
    ] == [
        3,
        4,
        5,
    ], emitted

    assert observer.previous_board_count == 5

    # Perception must not mutate semantic ownership.
    assert observer.hand.street == initial_street
    assert observer.hand.actions == initial_actions
    assert observer.hand.next_actor == initial_next_actor

    # A new observer starting mid-hand establishes a baseline.
    # It must not fabricate a boundary that was never observed.
    midhand = build_observer()

    with patch(
        "src.v017.frame_hand_observer.count_board_cards",
        return_value=3,
    ), patch(
        "src.v017.frame_hand_observer.hero_cards_visible",
        return_value=False,
    ):
        first = midhand.process_frame(
            frame.copy(),
            frame_id=100,
        )

    assert boundary_events(first) == []
    assert midhand.previous_board_count == 3
    assert midhand.hand.street == "PREFLOP"

    print(
        "G3.5A FRAME STREET BOUNDARY PERCEPTION: PASS"
    )
    print(
        "boundaries:",
        [
            (
                event["frame"],
                event["type"],
                event["board_count"],
            )
            for event in emitted
        ],
    )
    print(
        "semantic street unchanged:",
        observer.hand.street,
    )


if __name__ == "__main__":
    main()
