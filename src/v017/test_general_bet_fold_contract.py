from src.v017.hand_engine import HandEngine


def main():
    players = [
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
            "stack_bb": 50.0,
        },
        {
            "seat": "btn",
            "position": "BTN",
            "name": "BTN",
            "stack_bb": 60.0,
        },
    ]

    hand = HandEngine(
        players=players,
        action_order=[
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    # Finish preflop generically.
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

    # --------------------------------------------------------
    # Opening postflop commitment.
    # --------------------------------------------------------

    hand.start_street(
        "FLOP",
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

    action = hand.observe_stack_commitment(
        "bb",
        3.37,
    )

    print(
        "opening action =",
        action,
    )

    assert action == "BET"
    assert hand.current_price_bb == 3.37

    flop = [
        item
        for item in hand.semantic_actions()
        if item["street"] == "FLOP"
    ]

    assert flop[-1]["action"] == "BET"
    assert flop[-1]["amount_bb"] == 3.37
    assert flop[-1]["raise_to_bb"] is None

    # --------------------------------------------------------
    # Generic fold-return contract on a fresh street actor.
    # --------------------------------------------------------

    hand2 = HandEngine(
        players=players,
        action_order=[
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    folded = hand2.observe_cards_disappeared(
        "btn"
    )

    print(
        "fold return =",
        folded,
    )

    assert folded == "FOLD"
    assert hand2.players["btn"].folded is True
    assert hand2.next_actor == "hero"

    print()
    print(
        "V0.17 GENERAL BET/FOLD CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
