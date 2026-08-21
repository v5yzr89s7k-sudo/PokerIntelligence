from src.state.canonical_hand import CanonicalHand


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="observed-starting-pot-baseline",
        players=[
            {
                "seat": "sb",
                "name": "SB",
                "stack_bb": 100.0,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 100.0,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 100.0,
            },
        ],
        hero_cards=[],
        hero_position="SB",
        positions={
            "sb": "SB",
            "bb": "BB",
            "btn": "BTN",
        },
        started_ts=1.0,
    )


def add(
    hand,
    seat,
    action,
    amount=None,
    raise_to=None,
    ts=1.0,
):
    return hand.add_action(
        seat=seat,
        action=action,
        amount_bb=amount,
        raise_to_bb=raise_to,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=ts,
    )


def main():
    hand = make_hand()

    # Known forced contributions.
    add(
        hand,
        "sb",
        "POST_SMALL_BLIND",
        amount=0.5,
        ts=1.0,
    )

    add(
        hand,
        "bb",
        "POST_BIG_BLIND",
        amount=1.0,
        ts=1.1,
    )

    known_forced = hand.expected_pot_bb

    assert known_forced == 1.5

    # Arbitrary authoritative observed starting pot.
    #
    # It is intentionally larger than the forced contribution
    # ledger. The difference represents money already present
    # at the beginning of action whose exact semantic source
    # need not be reconstructed here.
    observed_start = 3.4

    hand.establish_starting_pot_adjustment(
        observed_start,
        known_forced,
    )

    hand.set_observed_pot(
        observed_start
    )

    summary = hand.street_summaries[
        "PREFLOP"
    ]

    assert hand.pot_bb == observed_start

    # First voluntary action: BTN raises to an arbitrary live
    # commitment of 2.6 BB.
    add(
        hand,
        "btn",
        "RAISE",
        raise_to=2.6,
        ts=2.0,
    )

    expected_after_raise = round(
        observed_start + 2.6,
        2,
    )

    print(
        "known forced:",
        known_forced,
    )

    print(
        "observed starting pot:",
        observed_start,
    )

    print(
        "expected after raise:",
        expected_after_raise,
    )

    print(
        "actual pot:",
        hand.pot_bb,
    )

    assert (
        abs(
            float(hand.pot_bb)
            - expected_after_raise
        )
        < 0.001
    ), (
        "REPRODUCED: canonical recomputation "
        "discarded money proven by the "
        "authoritative observed starting pot"
    )

    # SB already has 0.5 BB live. Calling the 2.6 BB price
    # adds only another 2.1 BB.
    add(
        hand,
        "sb",
        "CALL",
        amount=2.1,
        ts=3.0,
    )

    expected_after_sb = round(
        expected_after_raise + 2.1,
        2,
    )

    assert (
        abs(
            float(hand.pot_bb)
            - expected_after_sb
        )
        < 0.001
    )

    # BB already has 1.0 BB live, therefore another 1.6 BB.
    add(
        hand,
        "bb",
        "CALL",
        amount=1.6,
        ts=4.0,
    )

    expected_final = round(
        expected_after_sb + 1.6,
        2,
    )

    assert (
        abs(
            float(hand.pot_bb)
            - expected_final
        )
        < 0.001
    )

    assert (
        abs(
            float(
                summary.ending_pot_bb
            )
            - expected_final
        )
        < 0.001
    )

    print()
    print(
        "final expected:",
        expected_final,
    )

    print(
        "final actual:",
        hand.pot_bb,
    )

    print()
    print(
        "PASS: authoritative observed starting "
        "pot survives later canonical actions"
    )


if __name__ == "__main__":
    main()
