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

    # Complete a deterministic preflop round.
    engine.observe_cards_disappeared("lj")
    engine.observe_stack_commitment(
        "btn",
        2.0,
    )
    engine.observe_stack_commitment(
        "hero",
        1.5,
    )
    engine.observe_stack_commitment(
        "bb",
        1.0,
    )

    preflop_actions = list(
        engine.semantic_actions()
    )

    assert engine.players["lj"].folded is True
    assert engine.current_price_bb == 2.0

    print("===== END PREFLOP =====")
    print("street =", engine.street)
    print("price =", engine.current_price_bb)
    print("next_actor =", engine.next_actor)

    # Postflop order is supplied by poker-position/table state,
    # not inferred by the perception layer.
    engine.start_street(
        "FLOP",
        [
            "bb",
            "hero",
            "btn",
        ],
    )

    print()
    print("===== START FLOP =====")
    print("street =", engine.street)
    print("price =", engine.current_price_bb)
    print("next_actor =", engine.next_actor)

    assert engine.street == "FLOP"
    assert engine.current_price_bb == 0.0
    assert engine.next_actor == "bb"
    assert engine.players["lj"].folded is True

    for player in engine.players.values():
        assert player.street_commitment_bb == 0.0

    # Historical chronology must remain untouched.
    assert engine.semantic_actions() == preflop_actions

    # Folded players may not re-enter action order.
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
        print()
        print(
            "folded-seat guard =",
            str(exc),
        )
    else:
        raise AssertionError(
            "folded player incorrectly admitted to TURN"
        )

    # Failed transition must not mutate current street.
    assert engine.street == "FLOP"

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

    # Illegal backward/duplicate street transition.
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
        print()
        print(
            "chronology guard =",
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
