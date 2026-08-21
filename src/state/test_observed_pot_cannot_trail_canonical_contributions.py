from src.state.canonical_hand import CanonicalHand


def main():
    players = [
        {
            "seat": "a",
            "name": "",
            "stack_bb": 100.0,
        },
        {
            "seat": "b",
            "name": "",
            "stack_bb": 100.0,
        },
        {
            "seat": "c",
            "name": "",
            "stack_bb": 100.0,
        },
    ]

    hand = CanonicalHand().start_hand(
        hand_id="pot-floor-contract",
        players=players,
        hero_cards=[],
        hero_position="unknown",
        positions={},
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    # Establish mandatory contributions through the canonical action model.
    hand.add_action(
        seat="b",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=1.0,
    )

    hand.add_action(
        seat="c",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=1.0,
    )

    initial_expected = hand.expected_pot_bb

    # A real observed pot may legitimately be ahead of currently known
    # semantic contributions.
    hand.set_observed_pot(2.25)

    assert hand.pot_bb == 2.25

    # Later semantic evidence establishes additional contributions.
    # These values are intentionally arbitrary: this test is about the
    # accounting invariant, not one recorded poker hand.
    hand.add_action(
        seat="a",
        action="RAISE",
        raise_to_bb=3.0,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=2.0,
    )

    hand.add_action(
        seat="b",
        action="CALL",
        amount_bb=2.5,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=3.0,
    )

    hand.add_action(
        seat="c",
        action="CALL",
        amount_bb=2.0,
        confidence=1.0,
        source="test",
        evidence=[],
        ts=4.0,
    )

    expected = hand.expected_pot_bb

    print("initial expected:", initial_expected)
    print("stale observed pot:", 2.25)
    print("canonical expected:", expected)
    print("canonical pot_bb:", hand.pot_bb)

    summary = hand.street_summaries["PREFLOP"]

    print(
        "preflop ending:",
        summary.ending_pot_bb,
    )

    assert expected is not None
    assert expected > 2.25

    assert (
        float(hand.pot_bb or 0.0) >= expected
    ), (
        "REPRODUCED: earlier observed pot remains "
        "authoritative after canonical contributions "
        "prove a larger pot"
    )

    assert (
        float(summary.ending_pot_bb or 0.0) >= expected
    ), (
        "REPRODUCED: street ending pot remains below "
        "proven canonical contributions"
    )

    print()
    print(
        "PASS: street pot cannot trail "
        "canonical contributions"
    )


if __name__ == "__main__":
    main()
