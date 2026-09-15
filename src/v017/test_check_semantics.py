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
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 60.0,
    },
]


def build():
    return HandEngine(
        players=PLAYERS,
        action_order=[
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )


def close_preflop(hand):
    assert (
        hand.observe_cards_disappeared(
            "btn"
        )
        == "FOLD"
    )

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


def main():
    # --------------------------------------------------------
    # CHECK at zero price.
    # --------------------------------------------------------

    hand = build()
    close_preflop(hand)

    hand.start_street(
        "FLOP",
        [
            "hero",
            "bb",
        ],
    )

    print("===== ZERO-PRICE CHECK =====")

    action = hand.observe_no_commitment(
        "hero"
    )

    assert action == "CHECK"
    assert hand.next_actor == "bb"
    assert hand.current_price_bb == 0.0

    # BB checks too, legitimately closing the round.
    assert (
        hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert hand.next_actor is None

    # --------------------------------------------------------
    # CHECK while facing a real bet must fail.
    # --------------------------------------------------------

    hand.start_street(
        "TURN",
        [
            "hero",
            "bb",
        ],
    )

    assert (
        hand.observe_no_commitment(
            "hero"
        )
        == "CHECK"
    )

    assert (
        hand.observe_stack_commitment(
            "bb",
            2.0,
        )
        == "BET"
    )

    # Aggression must reopen action to Hero.
    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 2.0

    print()
    print("===== CHECK WHILE FACING BET =====")

    try:
        hand.observe_no_commitment(
            "hero"
        )
    except ValueError as exc:
        print(exc)
    else:
        raise AssertionError(
            "CHECK accepted while facing a bet"
        )

    # Rejected observation must not consume chronology.
    assert hand.next_actor == "hero"

    # Hero calls, legitimately closing TURN.
    assert (
        hand.observe_stack_commitment(
            "hero",
            2.0,
        )
        == "CALL"
    )

    assert hand.next_actor is None

    checks = [
        item
        for item in hand.semantic_actions()
        if item["action"] == "CHECK"
    ]

    assert [
        item["street"]
        for item in checks
    ] == [
        "PREFLOP",
        "FLOP",
        "FLOP",
        "TURN",
    ]

    print()
    print(
        "V0.17 CHECK SEMANTICS: PASS"
    )


if __name__ == "__main__":
    main()
