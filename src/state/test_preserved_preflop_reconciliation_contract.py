from src.state.canonical_hand import CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)


def make_hand():
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
        hand_id="preserved-preflop-contract",
        players=players,
        hero_cards=["Qd", "Ah"],
        hero_position="BB",
        positions=positions,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(positions)

    # Seed the same mandatory blinds already present in production.
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

    return hand


def main():
    hand = make_hand()

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

    # Canonical board advances before delayed PREFLOP reconstruction.
    hand.set_board(
        ["Jd", "9s", "Tc"],
        ts=10.0,
    )

    assert hand.current_street == "FLOP"

    flop_queue_before = list(hand.players_to_act)
    flop_bet_before = hand.current_bet_bb
    flop_aggressor_before = hand.last_aggressor_seat

    # Historical primitive already supports these non-aggressive actions.
    hand.add_boundary_action(
        street="PREFLOP",
        seat="utg",
        action="CALL",
        amount_bb=1.0,
        confidence=0.95,
        source="deferred_inferred_action",
        evidence=["stack_changed"],
        ts=2.0,
    )

    for index, seat in enumerate(
        ("hj", "co", "btn"),
        start=3,
    ):
        hand.add_boundary_action(
            street="PREFLOP",
            seat=seat,
            action="FOLD",
            confidence=0.98,
            source="preserved_preflop_reconciliation",
            evidence=["no_commitment_evidence"],
            ts=float(index),
        )

    hand.add_boundary_action(
        street="PREFLOP",
        seat="sb",
        action="RAISE",
        raise_to_bb=2.5,
        confidence=0.95,
        source="deferred_inferred_action",
        evidence=["stack_changed"],
        ts=6.0,
    )

    hand.add_boundary_action(
        street="PREFLOP",
        seat="hero",
        action="CALL",
        amount_bb=1.5,
        confidence=0.98,
        source="deferred_inferred_action",
        evidence=["stack_changed"],
        ts=7.0,
    )

    # Verify complete historical recovery remains isolated from FLOP.
    actions = [
        a
        for a in hand.actions
        if a.street == "PREFLOP"
    ]

    assert any(
        a.seat == "utg"
        and a.action == "CALL"
        and a.amount_bb == 1.0
        for a in actions
    )

    assert [
        a.seat
        for a in actions
        if a.action == "FOLD"
    ] == ["hj", "co", "btn"]

    sb_raise = next(
        a
        for a in actions
        if a.seat == "sb"
        and a.action == "RAISE"
    )

    assert sb_raise.raise_to_bb == 2.5

    hero_call = next(
        a
        for a in actions
        if a.seat == "hero"
        and a.action == "CALL"
    )

    assert hero_call.amount_bb == 1.5

    voluntary = [
        (
            a.seat,
            a.action,
            a.amount_bb,
            a.raise_to_bb,
        )
        for a in actions
        if a.action not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert voluntary == [
        ("utg", "CALL", 1.0, None),
        ("hj", "FOLD", None, None),
        ("co", "FOLD", None, None),
        ("btn", "FOLD", None, None),
        ("sb", "RAISE", None, 2.5),
        ("hero", "CALL", 1.5, None),
    ], voluntary

    assert (
        hand.players["sb"]
        .committed_by_street["PREFLOP"]
        == 2.5
    )

    assert (
        hand.players["hero"]
        .committed_by_street["PREFLOP"]
        == 2.5
    )

    assert hand.current_street == "FLOP"
    assert hand.players_to_act == flop_queue_before
    assert hand.current_bet_bb == flop_bet_before
    assert hand.last_aggressor_seat == flop_aggressor_before

    print(
        "PASS preserved preflop contract baseline: "
        "historical CALL/FOLD/RAISE/CALL recovery is isolated from FLOP"
    )


if __name__ == "__main__":
    main()
