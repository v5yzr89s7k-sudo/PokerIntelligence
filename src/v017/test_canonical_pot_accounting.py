from src.v017.hand_engine import HandEngine


def build():
    players = [
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

    return HandEngine(
        players=players,
        action_order=[
            "co",
            "btn",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
    )


def main():
    hand = build()

    assert hand.pot_bb == 1.5

    for seat in hand.players:
        hand.post_ante(
            seat,
            0.125,
        )

    # Current implementation stores canonical BB accounting
    # at centi-BB precision.
    assert hand.pot_bb == 2.0

    # Antes never alter betting commitments.
    assert hand.players["co"].street_commitment_bb == 0.0
    assert hand.players["btn"].street_commitment_bb == 0.0
    assert hand.players["sb"].street_commitment_bb == 0.5
    assert hand.players["bb"].street_commitment_bb == 1.0

    hand.observe_stack_commitment(
        "co",
        2.0,
    )
    assert hand.pot_bb == 4.0

    hand.observe_stack_commitment(
        "btn",
        2.0,
    )
    assert hand.pot_bb == 6.0

    hand.observe_stack_commitment(
        "sb",
        1.5,
    )
    assert hand.pot_bb == 7.5

    hand.observe_stack_commitment(
        "bb",
        1.0,
    )
    assert hand.pot_bb == 8.5

    assert hand.next_actor is None

    lifetime_before = {
        seat: player.total_contribution_bb
        for seat, player in hand.players.items()
    }

    hand.start_street(
        "FLOP",
        [
            "sb",
            "bb",
            "co",
            "btn",
        ],
        board=[
            "8s",
            "7d",
            "7s",
        ],
    )

    assert hand.pot_bb == 8.5

    for player in hand.players.values():
        assert player.street_commitment_bb == 0.0

    assert {
        seat: player.total_contribution_bb
        for seat, player in hand.players.items()
    } == lifetime_before

    hand.observe_no_commitment("sb")
    hand.observe_no_commitment("bb")
    hand.observe_no_commitment("co")
    hand.observe_no_commitment("btn")

    assert hand.pot_bb == 8.5

    print("INITIAL BLINDS OWNED: PASS")
    print("ANTE DOES NOT ALTER PRICE: PASS")
    print("VOLUNTARY CONTRIBUTIONS ACCUMULATE: PASS")
    print("STREET RESET PRESERVES POT: PASS")
    print("CHECK/FOLD ZERO CONTRIBUTION: PASS")
    print("V0.17 CANONICAL POT ACCOUNTING: PASS")


if __name__ == "__main__":
    main()
