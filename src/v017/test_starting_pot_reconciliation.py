from src.v017.hand_engine import HandEngine


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 100.0,
    },
    {
        "seat": "co",
        "position": "CO",
        "name": "CO",
        "stack_bb": 100.0,
    },
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 100.0,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 100.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 100.0,
    },
]


def build():
    return HandEngine(
        players=PLAYERS,
        action_order=[
            "utg",
            "co",
            "btn",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
    )


def main():
    print(
        "===== CASE A — PHYSICAL STARTING POT ====="
    )

    hand = build()

    assert hand.pot_bb == 1.5

    missing = hand.observe_starting_pot(
        2.5
    )

    print(
        "missing_forced =",
        missing,
    )
    print(
        "pot =",
        hand.pot_bb,
    )

    assert missing == 1.0
    assert hand.pot_bb == 2.5
    assert hand.starting_pot_bb == 2.5
    assert (
        hand.preacquisition_forced_pot_bb
        == 1.0
    )

    # The physical pot did not alter betting price.
    assert (
        hand.players["sb"]
        .street_commitment_bb
        == 0.5
    )
    assert (
        hand.players["bb"]
        .street_commitment_bb
        == 1.0
    )
    assert hand.current_price_bb == 1.0

    print(
        "PHYSICAL STARTING POT RECONCILED: PASS"
    )
    print(
        "BETTING PRICE UNCHANGED: PASS"
    )

    print()
    print(
        "===== CASE B — DUPLICATE REJECTED ====="
    )

    try:
        hand.observe_starting_pot(
            2.5
        )
    except ValueError as exc:
        print(
            "duplicate ->",
            exc,
        )
    else:
        raise AssertionError(
            "duplicate starting pot accepted"
        )

    print(
        "DUPLICATE RECONCILIATION: REJECTED"
    )

    print()
    print(
        "===== CASE C — TOO SMALL REJECTED ====="
    )

    hand = build()

    try:
        hand.observe_starting_pot(
            1.0
        )
    except ValueError as exc:
        print(
            "too small ->",
            exc,
        )
    else:
        raise AssertionError(
            "starting pot below blinds accepted"
        )

    print(
        "BELOW CANONICAL FORCED POT: REJECTED"
    )

    print()
    print(
        "===== CASE D — LATE RECONCILIATION REJECTED ====="
    )

    hand = build()

    action = hand.observe_cards_disappeared(
        "utg"
    )

    print(
        "voluntary_action =",
        action,
    )

    assert action == "FOLD"

    try:
        hand.observe_starting_pot(
            2.5
        )
    except ValueError as exc:
        print(
            "late ->",
            exc,
        )
    else:
        raise AssertionError(
            "late starting pot accepted"
        )

    print(
        "AFTER VOLUNTARY ACTION: REJECTED"
    )

    print()
    print(
        "V0.17 STARTING POT RECONCILIATION: PASS"
    )


if __name__ == "__main__":
    main()
