from copy import deepcopy

from src.v017.hand_engine import HandEngine
from src.v017.hand_projection import (
    project_hand,
)


def main():
    hand = HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 20.0,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 40.0,
            },
        ],
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    hand.observe_hero_cards(
        [
            "As",
            "Kd",
        ]
    )

    hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    hand.observe_no_commitment(
        "bb"
    )

    hand.start_street(
        "FLOP",
        [
            "hero",
            "bb",
        ],
        board=[
            "2c",
            "7d",
            "Jh",
        ],
    )

    before = {
        "hero_cards": deepcopy(
            hand.hero_cards
        ),
        "board": deepcopy(
            hand.board
        ),
        "actions": deepcopy(
            hand.semantic_actions()
        ),
        "pending": deepcopy(
            hand.pending_to_act
        ),
    }

    projection = project_hand(
        hand
    )

    after = {
        "hero_cards": deepcopy(
            hand.hero_cards
        ),
        "board": deepcopy(
            hand.board
        ),
        "actions": deepcopy(
            hand.semantic_actions()
        ),
        "pending": deepcopy(
            hand.pending_to_act
        ),
    }

    assert before == after

    assert projection[
        "hero_cards"
    ] == [
        "As",
        "Kd",
    ]

    assert projection[
        "board"
    ] == [
        "2c",
        "7d",
        "Jh",
    ]

    # Projection owns copies, not engine containers.
    projection["hero_cards"].append(
        "BAD"
    )
    projection["board"].append(
        "BAD"
    )

    assert hand.hero_cards == [
        "As",
        "Kd",
    ]

    assert hand.board == [
        "2c",
        "7d",
        "Jh",
    ]

    print(
        "V0.17 CARD PROJECTION READ-ONLY: PASS"
    )


if __name__ == "__main__":
    main()
