from copy import deepcopy

from src.v017.hand_engine import HandEngine


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
        "name": "BB",
        "stack_bb": 40.0,
    },
]


def build():
    return HandEngine(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )


def close_preflop(hand):
    assert (
        hand.observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )

    assert (
        hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert hand.next_actor is None


def close_street(hand):
    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert hand.next_actor is None


def main():
    hand = build()

    assert hand.hero_cards == []
    assert hand.board == []

    # Card strings are opaque identities to HandEngine.
    # Recognition/parsing belongs upstream.
    assert hand.observe_hero_cards(
        [
            "As",
            "Kd",
        ]
    ) == [
        "As",
        "Kd",
    ]

    # Idempotent same observation.
    assert hand.observe_hero_cards(
        [
            "As",
            "Kd",
        ]
    ) == [
        "As",
        "Kd",
    ]

    try:
        hand.observe_hero_cards(
            [
                "As",
                "Qc",
            ]
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Hero cards changed within hand"
        )

    close_preflop(hand)

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

    assert hand.board == [
        "2c",
        "7d",
        "Jh",
    ]

    close_street(hand)

    hand.start_street(
        "TURN",
        [
            "hero",
            "bb",
        ],
        board=[
            "2c",
            "7d",
            "Jh",
            "9s",
        ],
    )

    assert hand.board == [
        "2c",
        "7d",
        "Jh",
        "9s",
    ]

    close_street(hand)

    hand.start_street(
        "RIVER",
        [
            "hero",
            "bb",
        ],
        board=[
            "2c",
            "7d",
            "Jh",
            "9s",
            "3c",
        ],
    )

    assert hand.board == [
        "2c",
        "7d",
        "Jh",
        "9s",
        "3c",
    ]

    # --------------------------------------------------------
    # Invalid board mutations must not alter state.
    # --------------------------------------------------------

    bad = build()
    bad.observe_hero_cards(
        [
            "As",
            "Kd",
        ]
    )
    close_preflop(bad)

    before = deepcopy(
        bad.board
    )

    try:
        bad.start_street(
            "FLOP",
            [
                "hero",
                "bb",
            ],
            board=[
                "As",
                "7d",
                "Jh",
            ],
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Hero/board duplicate accepted"
        )

    assert bad.street == "PREFLOP"
    assert bad.board == before

    try:
        bad.start_street(
            "FLOP",
            [
                "hero",
                "bb",
            ],
            board=[
                "2c",
                "7d",
            ],
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "two-card flop accepted"
        )

    assert bad.street == "PREFLOP"
    assert bad.board == before

    print(
        "V0.17 OBJECTIVE CARD STATE: PASS"
    )


if __name__ == "__main__":
    main()
