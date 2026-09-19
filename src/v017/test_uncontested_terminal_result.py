from src.v017.hand_engine import HandEngine


def build_heads_up():
    return HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 23.28,
            },
            {
                "seat": "villain",
                "position": "BB",
                "name": "Villain",
                "stack_bb": 27.47,
            },
        ],
        action_order=[
            "hero",
            "villain",
        ],
        small_blind_seat="hero",
        big_blind_seat="villain",
    )


def main():
    # --------------------------------------------------------
    # Positive contract:
    #
    # A terminal fold leaves exactly one dealt-in,
    # non-folded player. HandEngine already owns every fact
    # required to establish the uncontested result.
    # --------------------------------------------------------
    hand = build_heads_up()

    assert hand.hand_complete is False
    assert hand.completion_reason is None
    assert hand.winner_seats == []

    assert hand.observe_fold("hero") == "FOLD"

    assert hand.next_actor is None

    assert hand.hand_complete is True
    assert hand.completion_reason == "UNCONTESTED"
    assert hand.winner_seats == ["villain"]

    # Winner identity is canonical seat identity, not display
    # text synthesized by presentation.
    winner = hand.players[hand.winner_seats[0]]

    assert winner.position == "BB"
    assert winner.name == "Villain"

    print(
        "terminal winner =",
        hand.winner_seats,
        winner.position,
        winner.name,
    )

    # --------------------------------------------------------
    # Negative contract:
    #
    # next_actor=None alone is NOT hand completion.
    #
    # Both players move all-in preflop. Betting is closed,
    # but no winner is known and the board has not run out.
    # --------------------------------------------------------
    allin = HandEngine(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 4.5,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 4.0,
            },
        ],
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )

    assert allin.observe_stack_commitment(
        "hero",
        4.5,
        all_in_confirmed=True,
    ) == "RAISE"

    assert allin.observe_stack_commitment(
        "bb",
        4.0,
        all_in_confirmed=True,
    ) == "CALL"

    assert allin.next_actor is None

    assert allin.hand_complete is False
    assert allin.completion_reason is None
    assert allin.winner_seats == []

    print(
        "all-in betting closed without result:",
        "next_actor=",
        allin.next_actor,
        "complete=",
        allin.hand_complete,
        "winners=",
        allin.winner_seats,
    )

    print()
    print(
        "V0.17 UNCONTESTED TERMINAL RESULT "
        "OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
