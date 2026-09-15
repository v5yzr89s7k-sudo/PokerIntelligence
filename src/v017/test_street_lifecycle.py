from src.v017.hand_engine import HandEngine


def build_engine():
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
            "stack_bb": 40.0,
        },
        {
            "seat": "lj",
            "position": "LJ",
            "name": "LJ",
            "stack_bb": 50.0,
        },
        {
            "seat": "btn",
            "position": "BTN",
            "name": "BTN",
            "stack_bb": 60.0,
        },
    ]

    return HandEngine(
        players=players,
        action_order=[
            "lj",
            "btn",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
    )


def main():
    engine = build_engine()

    # --------------------------------------------------------
    # Complete preflop legitimately.
    # --------------------------------------------------------

    assert (
        engine.observe_cards_disappeared(
            "lj"
        )
        == "FOLD"
    )

    assert (
        engine.observe_stack_commitment(
            "btn",
            2.0,
        )
        == "RAISE"
    )

    assert (
        engine.observe_stack_commitment(
            "hero",
            1.5,
        )
        == "CALL"
    )

    assert (
        engine.observe_stack_commitment(
            "bb",
            1.0,
        )
        == "CALL"
    )

    assert engine.next_actor is None

    preflop_actions = list(
        engine.semantic_actions()
    )

    print("===== END PREFLOP =====")
    print("street =", engine.street)
    print("next_actor =", engine.next_actor)

    # --------------------------------------------------------
    # FLOP
    # --------------------------------------------------------

    engine.start_street(
        "FLOP",
        [
            "bb",
            "hero",
            "btn",
        ],
    )

    assert engine.street == "FLOP"
    assert engine.current_price_bb == 0.0
    assert engine.next_actor == "bb"
    assert engine.players["lj"].folded is True

    for player in engine.players.values():
        assert player.street_commitment_bb == 0.0

    # Starting a new street while FLOP remains open must fail.
    try:
        engine.start_street(
            "TURN",
            [
                "bb",
                "hero",
                "btn",
            ],
        )
    except ValueError as exc:
        print(
            "open-street guard =",
            str(exc),
        )
    else:
        raise AssertionError(
            "TURN accepted while FLOP remained open"
        )

    assert engine.street == "FLOP"

    # Close FLOP.
    assert engine.observe_no_commitment("bb") == "CHECK"
    assert engine.observe_no_commitment("hero") == "CHECK"
    assert engine.observe_no_commitment("btn") == "CHECK"
    assert engine.next_actor is None

    # Folded player may not re-enter TURN.
    try:
        engine.start_street(
            "TURN",
            [
                "bb",
                "lj",
                "hero",
                "btn",
            ],
        )
    except ValueError as exc:
        print(
            "folded-seat guard =",
            str(exc),
        )
    else:
        raise AssertionError(
            "folded player admitted to TURN"
        )

    assert engine.street == "FLOP"

    # --------------------------------------------------------
    # TURN
    # --------------------------------------------------------

    engine.start_street(
        "TURN",
        [
            "bb",
            "hero",
            "btn",
        ],
    )

    assert engine.street == "TURN"
    assert engine.current_price_bb == 0.0
    assert engine.next_actor == "bb"

    assert engine.observe_no_commitment("bb") == "CHECK"
    assert engine.observe_no_commitment("hero") == "CHECK"
    assert engine.observe_no_commitment("btn") == "CHECK"
    assert engine.next_actor is None

    # --------------------------------------------------------
    # RIVER
    # --------------------------------------------------------

    engine.start_street(
        "RIVER",
        [
            "bb",
            "hero",
            "btn",
        ],
    )

    assert engine.street == "RIVER"
    assert engine.current_price_bb == 0.0
    assert engine.next_actor == "bb"

    # Historical preflop chronology must remain intact.
    observed_preflop = [
        item
        for item in engine.semantic_actions()
        if item["street"] == "PREFLOP"
    ]

    assert observed_preflop == preflop_actions

    # Duplicate/backward RIVER transition must fail.
    try:
        engine.start_street(
            "RIVER",
            [
                "bb",
                "hero",
                "btn",
            ],
        )
    except ValueError as exc:
        print(
            "river guard =",
            str(exc),
        )
    else:
        raise AssertionError(
            "duplicate RIVER transition accepted"
        )

    print()
    print(
        "V0.17 STREET LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
