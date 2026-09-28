from src.v017.hand_engine import HandEngine


def main():
    players = [
        {
            "seat": "hero",
            "position": "CO",
            "name": "Hero",
            "stack_bb": 99.76,
        },
        {
            "seat": "bb",
            "position": "BB",
            "name": "BB",
            "stack_bb": 96.64,
        },
    ]

    hand = HandEngine(
        players=players,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    hand.observe_stack_commitment(
        "hero",
        2.10,
    )
    hand.observe_stack_commitment(
        "bb",
        1.60,
    )

    assert hand.next_actor is None

    hand.start_street(
        "FLOP",
        ["bb", "hero"],
        board=["4s", "Qs", "6s"],
    )

    actions_before = list(
        hand.semantic_actions()
    )

    # Confirmed physical decrease after Hero's betting action was
    # already consumed. This is accounting evidence only.
    hand.observe_terminal_physical_commitment(
        "hero",
        2.12,
    )

    assert (
        hand.semantic_actions()
        == actions_before
    )

    assert (
        hand.unmatched_commitment_bb("hero")
        == 2.12
    )

    hand.observe_fold("bb")

    assert hand.hand_complete
    assert hand.winner_seats == ["hero"]

    returned = hand.observe_uncalled_return(
        "hero",
        2.12,
    )

    assert returned == 2.12

    assert (
        hand.unmatched_commitment_bb("hero")
        == 0.0
    )

    assert (
        hand.semantic_actions()[:-1]
        == actions_before
    )

    print("PHYSICAL COMMITMENT BETTING ACTION: NO")
    print("TERMINAL EXPOSURE 2.12 BB: OWNED")
    print("UNCALLED RETURN CONSUMES EXPOSURE: PASS")
    print("V0.17 TERMINAL PHYSICAL COMMITMENT ACCOUNTING: PASS")


if __name__ == "__main__":
    main()
