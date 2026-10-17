from unittest.mock import patch

import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "villain",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
            "board": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "villain": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="board-count-monotonic",
    )

    frame = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    observed = iter((0, 3, 2, 3))

    with patch(
        "src.v017.frame_hand_observer.count_board_cards",
        side_effect=lambda *args, **kwargs: next(observed),
    ):
        baseline = observer.process_frame(
            frame,
            frame_id=99,
        )

        first = observer.process_frame(
            frame,
            frame_id=100,
        )

        second = observer.process_frame(
            frame,
            frame_id=101,
        )

        third = observer.process_frame(
            frame,
            frame_id=102,
        )

    first_boundaries = [
        e
        for e in first.events
        if e["type"].endswith(
            "_BOUNDARY_PHYSICAL"
        )
    ]

    second_boundaries = [
        e
        for e in second.events
        if e["type"].endswith(
            "_BOUNDARY_PHYSICAL"
        )
    ]

    third_boundaries = [
        e
        for e in third.events
        if e["type"].endswith(
            "_BOUNDARY_PHYSICAL"
        )
    ]

    assert [
        e["type"]
        for e in first_boundaries
    ] == [
        "FLOP_BOUNDARY_PHYSICAL"
    ]

    assert second_boundaries == []

    assert third_boundaries == [], (
        "RED: transient 3 -> 2 -> 3 board count "
        "fabricated a second FLOP boundary"
    )

    assert observer.previous_board_count == 3, (
        "RED: physical board chronology regressed "
        "below already-established flop"
    )

    print(
        "BOARD COUNT 3 -> 2 -> 3 "
        "CANNOT DUPLICATE FLOP: PASS"
    )


if __name__ == "__main__":
    main()
