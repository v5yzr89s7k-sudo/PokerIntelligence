from src.v017.hand_engine import HandEngine


def main():
    hand = HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 5.0,
                "dealt_in": True,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 5.0,
                "dealt_in": True,
            },
        ],
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    # Hero moves all-in to 5 BB.
    assert hand.observe_stack_commitment(
        "hero",
        4.5,
        all_in_confirmed=True,
    ) == "RAISE"

    assert hand.players["hero"].all_in is True

    print(
        "after Hero all-in raise =",
        hand.pending_to_act,
    )

    assert hand.pending_to_act == ["bb"]

    # BB calls all-in for its remaining 4 BB.
    assert hand.observe_stack_commitment(
        "bb",
        4.0,
        all_in_confirmed=True,
    ) == "CALL"

    assert hand.players["bb"].all_in is True
    assert hand.next_actor is None

    print(
        "after BB all-in call =",
        hand.pending_to_act,
    )

    # Caller intentionally supplies both seats at every boundary.
    # HandEngine owns final actionability and must filter both.
    hand.start_street(
        "FLOP",
        ["hero", "bb"],
        board=["As", "7d", "2c"],
    )

    print(
        "FLOP pending =",
        hand.pending_to_act,
    )

    assert hand.pending_to_act == []
    assert hand.next_actor is None

    hand.start_street(
        "TURN",
        ["hero", "bb"],
        board=["As", "7d", "2c", "Kh"],
    )

    print(
        "TURN pending =",
        hand.pending_to_act,
    )

    assert hand.pending_to_act == []
    assert hand.next_actor is None

    hand.start_street(
        "RIVER",
        ["hero", "bb"],
        board=["As", "7d", "2c", "Kh", "9s"],
    )

    print(
        "RIVER pending =",
        hand.pending_to_act,
    )

    assert hand.pending_to_act == []
    assert hand.next_actor is None

    semantic = tuple(
        (
            action.street,
            action.seat,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in hand.actions
    )

    print("semantic actions =", semantic)

    # Board runout must not manufacture CHECKs or any other
    # betting actions.
    assert semantic == (
        (
            "PREFLOP",
            "hero",
            "POST_SMALL_BLIND",
            0.5,
            None,
        ),
        (
            "PREFLOP",
            "bb",
            "POST_BIG_BLIND",
            1.0,
            None,
        ),
        (
            "PREFLOP",
            "hero",
            "RAISE",
            None,
            5.0,
        ),
        (
            "PREFLOP",
            "bb",
            "CALL",
            4.0,
            None,
        ),
    )

    assert hand.street == "RIVER"
    assert hand.board == [
        "As",
        "7d",
        "2c",
        "Kh",
        "9s",
    ]

    print()
    print(
        "V0.17 ALL-IN AUTOMATIC "
        "BOARD RUNOUT: PASS"
    )


if __name__ == "__main__":
    main()
