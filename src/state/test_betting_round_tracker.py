from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
    CALL,
    FOLD_OR_RESOLVED,
    POST_SMALL_BLIND,
    POST_BIG_BLIND,
)
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="tracker-test",
        players=[
            {"seat": "seat_top", "name": "Alice", "stack_bb": 40},
            {"seat": "seat_upper_right", "name": "Bob", "stack_bb": 35},
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 30,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Ks"],
        hero_position="BTN",
        positions={
            "seat_top": "UTG",
            "seat_upper_right": "HJ",
            "hero": "BTN",
        },
        started_ts=1000.0,
    )


def inferred(
    episode_id,
    seat,
    action,
    street="PREFLOP",
    confidence=0.8,
):
    return InferredAction(
        episode_id=episode_id,
        seat=seat,
        street=street,
        action=action,
        confidence=confidence,
        evidence=["test_evidence"],
        reason="test",
        measurements={},
    )


def test_preflop_commitment_preserves_unresolved_semantic():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(1, "seat_top", BET_OR_RAISE)
    )

    assert result is not None
    assert result.action == BET_OR_RAISE
    assert len(hand.actions) == 1
    assert hand.last_aggressor_seat is None
    assert tracker.decisions[-1].accepted is True
    assert tracker.decisions[-1].canonical_action == BET_OR_RAISE


def test_second_postflop_commitment_preserves_unresolved_semantic():
    hand = make_hand()
    hand.set_board(["Ah", "7c", "2d"])
    tracker = BettingRoundTracker(hand)

    first = tracker.ingest(
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
            street="FLOP",
        )
    )
    result = tracker.ingest(
        inferred(
            2,
            "seat_upper_right",
            BET_OR_RAISE,
            street="FLOP",
        )
    )

    assert first is not None
    assert first.action == BET_OR_RAISE
    assert result is not None
    assert result.action == BET_OR_RAISE
    assert len(hand.actions) == 2
    assert hand.last_aggressor_seat is None
    assert tracker.decisions[-1].accepted is True
    assert (
        tracker.decisions[-1].canonical_action
        == BET_OR_RAISE
    )


def test_call_is_preserved():
    hand = make_hand()
    hand.set_board(["Ah", "7c", "2d"])
    tracker = BettingRoundTracker(hand)

    opening_bet = tracker.ingest(
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
            street="FLOP",
        )
    )
    result = tracker.ingest(
        inferred(
            2,
            "hero",
            CALL,
            street="FLOP",
        )
    )

    assert opening_bet is not None
    assert opening_bet.action == BET_OR_RAISE
    assert result is not None
    assert result.action == "CALL"
    assert result.sequence == 2


def test_ambiguous_fold_stays_diagnostics_only():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(1, "seat_top", FOLD_OR_RESOLVED)
    )

    assert result is None
    assert len(hand.actions) == 0
    assert hand.players["seat_top"].folded is False
    assert hand.players["seat_top"].active is True
    assert tracker.decisions[-1].accepted is False
    assert tracker.decisions[-1].canonical_action is None


def test_unknown_stays_diagnostics_only():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(1, "seat_top", "UNKNOWN")
    )

    assert result is None
    assert len(hand.actions) == 0
    assert tracker.decisions[-1].accepted is False
    assert tracker.decisions[-1].canonical_action is None


def test_unsupported_action_stays_diagnostics_only():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(1, "seat_top", "CHECK_OR_NOISE")
    )

    assert result is None
    assert len(hand.actions) == 0
    assert tracker.decisions[-1].accepted is False
    assert tracker.decisions[-1].canonical_action is None


def test_duplicate_episode_is_ignored():
    hand = make_hand()
    hand.set_board(["Ah", "7c", "2d"])
    tracker = BettingRoundTracker(hand)

    action = inferred(
        1,
        "seat_top",
        BET_OR_RAISE,
        street="FLOP",
    )

    first = tracker.ingest(action)
    duplicate = tracker.ingest(action)

    assert first is not None
    assert first.action == BET_OR_RAISE
    assert duplicate is None
    assert len(hand.actions) == 1


def test_street_change_resets_aggression():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    tracker.ingest(
        inferred(1, "seat_top", BET_OR_RAISE)
    )

    hand.set_board(["Ah", "7c", "2d"])

    result = tracker.ingest(
        inferred(
            2,
            "seat_upper_right",
            BET_OR_RAISE,
            street="FLOP",
        )
    )

    assert result is not None
    assert result.street == "FLOP"
    assert result.action == BET_OR_RAISE


def test_stale_street_action_is_rejected():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
            street="FLOP",
        )
    )

    assert result is None
    assert len(hand.actions) == 0
    assert tracker.decisions[-1].accepted is False


def test_order_is_preserved():
    hand = make_hand()
    hand.set_board(["Ah", "7c", "2d"])
    tracker = BettingRoundTracker(hand)

    tracker.ingest_many([
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
            street="FLOP",
        ),
        inferred(
            2,
            "seat_upper_right",
            CALL,
            street="FLOP",
        ),
        inferred(
            3,
            "hero",
            CALL,
            street="FLOP",
        ),
    ])

    assert [a.sequence for a in hand.actions] == [1, 2, 3]
    assert [a.action for a in hand.actions] == [
        BET_OR_RAISE,
        "CALL",
        "CALL",
    ]


def test_action_consumes_queue_through_actor():
    hand = make_hand()

    assert hand.players_to_act == [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]

    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
        )
    )

    assert result is not None

    # seat_top was skipped before the first voluntary preflop action and
    # is therefore recorded as a conservatively inferred fold.
    assert hand.players_to_act == [
        "hero",
    ]

    assert [
        (action.seat, action.action)
        for action in hand.actions
    ] == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", BET_OR_RAISE),
    ]

    inferred_fold = hand.actions[0]

    assert inferred_fold.source == "passive_inference"
    assert inferred_fold.confidence == 0.90
    assert inferred_fold.evidence == [
        "skipped_before_first_preflop_action",
    ]


def test_first_actor_consumes_only_itself():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
        )
    )

    assert result is not None
    assert hand.players_to_act == [
        "seat_upper_right",
        "hero",
    ]


def test_actor_outside_queue_does_not_corrupt_queue():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    original_queue = list(hand.players_to_act)

    result = tracker.ingest(
        inferred(
            1,
            "seat_lower_left",
            BET_OR_RAISE,
        )
    )

    assert result is not None
    assert hand.players_to_act == original_queue


def test_postflop_skipped_seat_is_not_inferred_as_fold():
    hand = make_hand()
    hand.set_board(["Ah", "7c", "2d"])
    tracker = BettingRoundTracker(hand)

    result = tracker.ingest(
        inferred(
            1,
            "seat_upper_right",
            BET_OR_RAISE,
            street="FLOP",
        )
    )

    assert result is not None

    assert [
        (action.seat, action.action)
        for action in hand.actions
    ] == [
        ("seat_upper_right", BET_OR_RAISE),
    ]

    assert hand.players["seat_top"].folded is False
    assert hand.players["seat_top"].active is True


def test_later_preflop_gap_is_not_inferred_without_more_context():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    first = tracker.ingest(
        inferred(
            1,
            "seat_top",
            BET_OR_RAISE,
        )
    )

    second = tracker.ingest(
        inferred(
            2,
            "hero",
            CALL,
        )
    )

    assert first is not None
    assert second is not None

    assert [
        (action.seat, action.action)
        for action in hand.actions
    ] == [
        ("seat_top", BET_OR_RAISE),
        ("hero", "CALL"),
    ]

    assert hand.players["seat_upper_right"].folded is False
    assert hand.players["seat_upper_right"].active is True


def test_forced_blinds_do_not_consume_preflop_queue():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    original_queue = list(hand.players_to_act)

    small_blind = inferred(
        1,
        "seat_upper_right",
        POST_SMALL_BLIND,
    )
    big_blind = inferred(
        2,
        "hero",
        POST_BIG_BLIND,
    )

    assert tracker.ingest(small_blind) is not None
    assert tracker.ingest(big_blind) is not None

    assert hand.players_to_act == original_queue


if __name__ == "__main__":
    tests = [
        test_preflop_commitment_preserves_unresolved_semantic,
        test_second_postflop_commitment_preserves_unresolved_semantic,
        test_call_is_preserved,
        test_ambiguous_fold_stays_diagnostics_only,
        test_unknown_stays_diagnostics_only,
        test_unsupported_action_stays_diagnostics_only,
        test_duplicate_episode_is_ignored,
        test_street_change_resets_aggression,
        test_stale_street_action_is_rejected,
        test_order_is_preserved,
        test_action_consumes_queue_through_actor,
        test_first_actor_consumes_only_itself,
        test_actor_outside_queue_does_not_corrupt_queue,
        test_postflop_skipped_seat_is_not_inferred_as_fold,
        test_later_preflop_gap_is_not_inferred_without_more_context,
        test_forced_blinds_do_not_consume_preflop_queue,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print("ALL BETTING ROUND TRACKER TESTS PASSED")
