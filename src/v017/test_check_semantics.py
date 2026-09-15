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


def main():
    hand = build()

    # Close preflop without changing the contract under test.
    hand.observe_cards_disappeared("btn")
    hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    hand.observe_no_commitment("bb")

    hand.start_street(
        "FLOP",
        [
            "hero",
            "bb",
        ],
    )

    print("===== OPEN FLOP =====")
    print("price =", hand.current_price_bb)
    print("next =", hand.next_actor)

    action = hand.observe_no_commitment(
        "hero"
    )

    assert action == "CHECK"
    assert hand.next_actor == "bb"
    assert hand.current_price_bb == 0.0

    action = hand.observe_stack_commitment(
        "bb",
        2.0,
    )

    assert action == "BET"
    assert hand.current_price_bb == 2.0

    print()
    print("===== CHECK WHILE FACING BET =====")

    # Start another street so Hero is first, then create a price
    # without allowing Hero to consume chronology.
    hand.start_street(
        "TURN",
        [
            "hero",
            "bb",
        ],
    )

    hand.current_price_bb = 2.0

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

    assert hand.next_actor == "hero"

    checks = [
        item
        for item in hand.semantic_actions()
        if item["action"] == "CHECK"
    ]

    assert len(checks) == 2
    assert checks[0]["street"] == "PREFLOP"
    assert checks[1]["street"] == "FLOP"

    print()
    print("V0.17 CHECK SEMANTICS: PASS")


if __name__ == "__main__":
    main()
