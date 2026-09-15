from copy import deepcopy

from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="v016-resolution-only",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={
            "hero": "BTN",
            "villain": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    return hand


def hand_snapshot(hand):
    return {
        "actions": [
            action.to_dict()
            for action in hand.actions
        ],
        "players_to_act": list(
            hand.players_to_act or []
        ),
        "current_bet_bb": hand.current_bet_bb,
        "last_aggressor_seat": (
            hand.last_aggressor_seat
        ),
        "players": {
            seat: {
                "folded": player.folded,
                "all_in": player.all_in,
                "active": player.active,
                "committed_by_street": deepcopy(
                    player.committed_by_street
                ),
            }
            for seat, player
            in hand.players.items()
        },
    }


def tracker_snapshot(tracker):
    return {
        "processed_episode_ids": set(
            tracker.processed_episode_ids
        ),
        "has_open_bet": tracker.has_open_bet,
        "last_aggressor_seat": (
            tracker.last_aggressor_seat
        ),
        "decisions": [
            item.to_dict()
            if hasattr(item, "to_dict")
            else repr(item)
            for item in tracker.decisions
        ],
        "commitment": tracker.commitment_tracker.to_dict(),
    }


def assert_unchanged(
    before_hand,
    after_hand,
    before_tracker,
    after_tracker,
):
    assert after_hand == before_hand, (
        "RED: resolution mutated CanonicalHand"
    )

    assert after_tracker == before_tracker, (
        "RED: resolution mutated betting tracker state"
    )


def test_opening_bet_resolves_without_mutation():
    hand = make_hand()

    hand.players_to_act = ["hero", "villain"]

    tracker = BettingRoundTracker(hand)

    before_hand = hand_snapshot(hand)
    before_tracker = tracker_snapshot(tracker)

    result = tracker.resolve_inferred_action({
        "episode_id": 101,
        "street": "PREFLOP",
        "seat": "hero",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "evidence": ["stack_changed"],
        "ts": 10.0,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.5,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "agreement_verified",
            },
        },
    })

    print()
    print("===== OPENING BET RESOLUTION =====")
    print(result)

    assert result is not None
    assert result["resolved"] is True
    assert result["seat"] == "hero"
    assert result["street"] == "PREFLOP"
    assert result["action"] in {
        "BET",
        "RAISE",
    }
    assert (
        result.get("amount_bb") is not None
        or result.get("raise_to_bb") is not None
    )

    assert_unchanged(
        before_hand,
        hand_snapshot(hand),
        before_tracker,
        tracker_snapshot(tracker),
    )

    print(
        "PASS: quantitative semantic/sizing "
        "resolution is mutation-free"
    )


def test_unresolved_chronology_does_not_mutate():
    hand = make_hand()

    hand.players_to_act = [
        "villain",
        "hero",
    ]

    tracker = BettingRoundTracker(hand)

    # Match the durable tracker queue as production does.
    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["villain", "hero"],
    )

    before_hand = hand_snapshot(hand)
    before_tracker = tracker_snapshot(tracker)

    result = tracker.resolve_inferred_action({
        "episode_id": 102,
        "street": "PREFLOP",
        "seat": "hero",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "evidence": ["stack_changed"],
        "ts": 11.0,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.5,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "agreement_verified",
            },
        },
    })

    print()
    print("===== CHRONOLOGY BLOCKED RESOLUTION =====")
    print(result)

    assert result is not None
    assert result["resolved"] is False
    assert result["reason"] == (
        "earlier actors remain unresolved"
    )
    assert result["earlier_seats"] == [
        "villain",
    ]

    assert_unchanged(
        before_hand,
        hand_snapshot(hand),
        before_tracker,
        tracker_snapshot(tracker),
    )

    print(
        "PASS: unresolved chronology remains "
        "mutation-free"
    )


def test_duplicate_resolution_does_not_claim_processing():
    hand = make_hand()

    hand.players_to_act = [
        "hero",
        "villain",
    ]

    tracker = BettingRoundTracker(hand)

    event = {
        "episode_id": 103,
        "street": "PREFLOP",
        "seat": "hero",
        "action": "CALL",
        "confidence": 0.95,
        "evidence": ["stack_changed"],
        "ts": 12.0,
        "measurements": {
            "stack_change": {
                "delta_bb": 1.0,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "agreement_verified",
            },
        },
    }

    before = set(
        tracker.processed_episode_ids
    )

    tracker.resolve_inferred_action(event)
    tracker.resolve_inferred_action(event)

    after = set(
        tracker.processed_episode_ids
    )

    assert after == before, (
        "resolution-only phase claimed "
        "processed episode ownership"
    )

    print(
        "PASS: resolution phase does not own "
        "episode acceptance/deduplication"
    )


def main():
    tests = [
        test_opening_bet_resolves_without_mutation,
        test_unresolved_chronology_does_not_mutate,
        test_duplicate_resolution_does_not_claim_processing,
    ]

    failures = []

    for test in tests:
        try:
            test()
        except (
            AssertionError,
            AttributeError,
        ) as exc:
            print()
            print(
                f"EXPECTED RED {test.__name__}"
            )
            print(exc)

            failures.append(
                (
                    test.__name__,
                    str(exc),
                )
            )

    print()
    print("===== FAILURES =====")

    for name, reason in failures:
        print(
            f"{name}: {reason}"
        )

    assert not failures, (
        "mutation-free betting resolution "
        f"contract failures: {failures}"
    )

    print()
    print(
        "PASS BettingRoundTracker mutation-free "
        "resolution contract"
    )


if __name__ == "__main__":
    main()
