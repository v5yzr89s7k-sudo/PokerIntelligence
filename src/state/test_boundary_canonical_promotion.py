from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="boundary-promotion-test",
        players=[
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "villain": "BTN",
            "hero": "BB",
        },
        started_ts=100.0,
    )

    return hand


def test_old_street_fold_does_not_corrupt_live_street():
    hand = make_hand()

    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=200.0,
    )

    assert hand.current_street == "FLOP"

    live_queue_before = list(hand.players_to_act)

    hand.current_bet_bb = 3.0
    hand.last_aggressor_seat = "hero"

    action = hand.add_boundary_action(
        street="PREFLOP",
        seat="villain",
        action="FOLD",
        confidence=0.98,
        source="boundary_stack_resolution",
        evidence=[
            "trusted_terminal_stack",
            "owed_response_at_boundary",
        ],
        ts=199.0,
    )

    assert action.street == "PREFLOP"
    assert action.action == "FOLD"

    assert hand.current_street == "FLOP"
    assert hand.current_bet_bb == 3.0
    assert hand.last_aggressor_seat == "hero"

    assert hand.players["villain"].folded is True
    assert hand.players["villain"].active is False

    # Historical promotion must not rewrite the already-established live
    # traversal queue. Queue reconciliation belongs to betting-state logic.
    assert hand.players_to_act == live_queue_before


def test_old_street_call_updates_only_historical_commitment():
    hand = make_hand()

    hand.players["villain"].committed_by_street["PREFLOP"] = 2.0

    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=200.0,
    )

    hand.current_bet_bb = 4.0
    hand.last_aggressor_seat = "hero"

    action = hand.add_boundary_action(
        street="PREFLOP",
        seat="villain",
        action="CALL",
        amount_bb=3.0,
        confidence=0.98,
        source="boundary_stack_resolution",
        evidence=["trusted_terminal_stack"],
        ts=199.0,
    )

    assert action.street == "PREFLOP"
    assert action.amount_bb == 3.0

    assert (
        hand.players["villain"]
        .committed_by_street["PREFLOP"]
        == 5.0
    )

    assert hand.current_street == "FLOP"
    assert hand.current_bet_bb == 4.0
    assert hand.last_aggressor_seat == "hero"


def test_boundary_promotion_is_idempotent():
    hand = make_hand()

    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=200.0,
    )

    first = hand.add_boundary_action(
        street="PREFLOP",
        seat="villain",
        action="FOLD",
        confidence=0.98,
        source="boundary_stack_resolution",
        ts=199.0,
    )

    second = hand.add_boundary_action(
        street="PREFLOP",
        seat="villain",
        action="FOLD",
        confidence=0.98,
        source="boundary_stack_resolution",
        ts=199.0,
    )

    assert first is second

    matches = [
        action
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.seat == "villain"
        and action.action == "FOLD"
        and action.source == "boundary_stack_resolution"
    ]

    assert len(matches) == 1


def test_boundary_raise_requires_explicit_sizing():
    hand = make_hand()

    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=200.0,
    )

    live_queue_before = list(hand.players_to_act)
    live_bet_before = hand.current_bet_bb
    live_aggressor_before = hand.last_aggressor_seat

    try:
        hand.add_boundary_action(
            street="PREFLOP",
            seat="villain",
            action="RAISE",
        )
    except ValueError as exc:
        assert (
            "boundary_raise_requires_explicit_raise_to_bb"
            in str(exc)
        )
    else:
        raise AssertionError(
            "historical RAISE without explicit sizing must fail"
        )

    action = hand.add_boundary_action(
        street="PREFLOP",
        seat="villain",
        action="RAISE",
        raise_to_bb=10.0,
        confidence=0.98,
        source="deferred_inferred_action",
    )

    assert action.street == "PREFLOP"
    assert action.action == "RAISE"
    assert action.raise_to_bb == 10.0

    assert hand.current_street == "FLOP"
    assert hand.players_to_act == live_queue_before
    assert hand.current_bet_bb == live_bet_before
    assert hand.last_aggressor_seat == live_aggressor_before


if __name__ == "__main__":
    test_old_street_fold_does_not_corrupt_live_street()
    test_old_street_call_updates_only_historical_commitment()
    test_boundary_promotion_is_idempotent()
    test_boundary_raise_requires_explicit_sizing()

    print(
        "PASS boundary canonical promotion: "
        "trusted historical FOLD/CALL can be promoted without "
        "corrupting current-street betting state"
    )
