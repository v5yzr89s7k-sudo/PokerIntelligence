from src.v017.hand_engine import HandEngine


def build():
    return HandEngine(
        players=[
            {
                "seat": "short",
                "position": "UTG",
                "name": "Short",
                "stack_bb": 0.4,
                "dealt_in": True,
            },
            {
                "seat": "hero",
                "position": "BTN",
                "name": "Hero",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
            {
                "seat": "sb",
                "position": "SB",
                "name": "SB",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 50.0,
                "dealt_in": True,
            },
        ],
        action_order=[
            "short",
            "hero",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
    )


def main():
    hand = build()

    # Independently-confirmed below-price commitment.
    action = hand.observe_stack_commitment(
        "short",
        0.4,
        all_in_confirmed=True,
    )

    assert action == "CALL"

    # HandEngine must persist the semantic fact after accepting
    # independently-confirmed all-in authority.
    assert hand.players["short"].all_in is True

    # Continue chronology until Hero raises. The all-in player
    # must never be reopened by aggression.
    assert hand.observe_stack_commitment(
        "hero",
        2.0,
    ) == "RAISE"

    print(
        "pending after Hero raise =",
        hand.pending_to_act,
    )

    assert "short" not in hand.pending_to_act, (
        "all-in player was reopened by aggression"
    )

    assert hand.observe_cards_disappeared(
        "sb"
    ) == "FOLD"

    assert hand.observe_stack_commitment(
        "bb",
        1.0,
    ) == "CALL"

    assert hand.next_actor is None

    # Even if a caller accidentally supplies the all-in seat,
    # HandEngine must not make that seat actionable again.
    hand.start_street(
        "FLOP",
        [
            "bb",
            "short",
            "hero",
        ],
        board=[
            "As",
            "7d",
            "2c",
        ],
    )

    print(
        "FLOP pending =",
        hand.pending_to_act,
    )

    assert hand.pending_to_act == [
        "bb",
        "hero",
    ], (
        "all-in player re-entered future street"
    )

    assert hand.next_actor == "bb"

    print()
    print(
        "V0.17 PERSISTENT ALL-IN "
        "ACTIONABILITY: PASS"
    )


if __name__ == "__main__":
    main()
