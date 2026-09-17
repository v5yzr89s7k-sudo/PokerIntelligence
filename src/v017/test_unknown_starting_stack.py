"""
Unknown starting stacks must not block semantic hand construction.

They remain presentation-unknown and have no quantitative authority.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)
from src.v017.current_hand_renderer import (
    render_current_hand,
)


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
        "stack_bb": None,
    },
]


def main():
    observer = FrameHandObserver(
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
        trusted_stacks={
            "hero": 20.0,
        },
        opponent_seats=[
            "bb",
        ],
        quantitative_seats=[
            "hero",
        ],
        hero_seat="hero",
        hand_id="unknown-stack-contract",
    )

    assert (
        observer.hand.players[
            "bb"
        ].starting_stack_bb
        is None
    )

    assert "bb" not in (
        observer.trusted_stacks
    )

    assert "bb" not in (
        observer.quantitative_seats
    )

    text = render_current_hand(
        observer.hand,
        hand_id="unknown-stack-contract",
    )

    assert "unknown" in text

    # Semantic chronology remains fully available.
    assert observer.hand.next_actor == "hero"

    print(
        "V0.17 UNKNOWN STARTING STACK: PASS"
    )


if __name__ == "__main__":
    main()
