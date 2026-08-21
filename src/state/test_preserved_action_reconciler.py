from src.state.canonical_hand import CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)
from src.state.preserved_action_reconciler import (
    reconcile_preserved_actions,
)


def main():
    players = [
        {"seat": "utg", "name": "UTG", "stack_bb": 48.57},
        {"seat": "hj", "name": "HJ", "stack_bb": 59.08},
        {"seat": "co", "name": "CO", "stack_bb": 106.70},
        {"seat": "btn", "name": "BTN", "stack_bb": 136.01},
        {"seat": "sb", "name": "SB", "stack_bb": 58.55},
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 11.78,
            "is_hero": True,
        },
    ]

    positions = {
        "utg": "UTG",
        "hj": "HJ",
        "co": "CO",
        "btn": "BTN",
        "sb": "SB",
        "hero": "BB",
    }

    hand = CanonicalHand().start_hand(
        hand_id="reconcile-test",
        players=players,
        hero_cards=["Qd", "Ah"],
        hero_position="BB",
        positions=positions,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(positions)
    hand.current_street = "PREFLOP"

    hand.add_action(
        seat="sb",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="test",
        ts=1.0,
    )

    hand.add_action(
        seat="hero",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="test",
        ts=1.0,
    )

    tracker = StreetCommitmentTracker()

    order = [
        "utg",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    tracker.initialize_street_order(
        "PREFLOP",
        order,
    )

    tracker.sync_queue(
        "PREFLOP",
        order,
    )

    # Objective commitment evidence arrived before semantic actions.
    for seat in ("utg", "sb", "hero"):
        tracker.record_commitment(
            "PREFLOP",
            seat,
        )

    qualified = {
        "utg": {
            "street": "PREFLOP",
            "seat": "utg",
            "action": "CALL_OR_RAISE",
            "delta_bb": 1.0,
            "confidence": 0.98,
            "evidence": ["stack_changed"],
            "ts": 2.0,
        },
        "sb": {
            "street": "PREFLOP",
            "seat": "sb",
            "action": "BET_OR_RAISE",
            "delta_bb": 2.0,
            "confidence": 0.98,
            "evidence": [
                "stack_changed",
                "bet_region_occupied",
            ],
            "ts": 6.0,
        },
        "hero": {
            "street": "PREFLOP",
            "seat": "hero",
            "action": "CALL_OR_RAISE",
            "delta_bb": 1.5,
            "confidence": 0.98,
            "evidence": ["stack_changed"],
            "ts": 7.0,
        },
    }

    result = reconcile_preserved_actions(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        qualified_actions=qualified,
    )

    assert result.resolved, result.reason

    observed = [
        (
            item["seat"],
            item["action"],
            item["amount_bb"],
            item["raise_to_bb"],
        )
        for item in result.actions
    ]

    expected = [
        ("utg", "CALL", 1.0, None),
        ("hj", "FOLD", None, None),
        ("co", "FOLD", None, None),
        ("btn", "FOLD", None, None),
        ("sb", "RAISE", None, 2.5),
        ("hero", "CALL", 1.5, None),
    ]

    assert observed == expected, observed

    # Missing semantic evidence for a committed player must block recovery.
    incomplete = dict(qualified)
    incomplete.pop("utg")

    blocked = reconcile_preserved_actions(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        qualified_actions=incomplete,
    )

    assert not blocked.resolved
    assert "utg" in blocked.reason

    print(
        "PASS preserved action reconciler: "
        "qualified actions recover CALL/FOLD/RAISE/CALL in poker order; "
        "committed actor without semantic evidence remains blocking"
    )


if __name__ == "__main__":
    main()
