from copy import deepcopy

from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="resolver-ingest-equivalence",
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


def event(
    episode_id,
    seat,
    action,
    delta_bb,
):
    return {
        "episode_id": episode_id,
        "street": "PREFLOP",
        "seat": seat,
        "action": action,
        "confidence": 0.95,
        "evidence": ["stack_changed"],
        "ts": float(episode_id),
        "measurements": {
            "stack_change": {
                "delta_bb": delta_bb,
                "stack_read_confidence": 0.98,
                "stack_read_mode": (
                    "agreement_verified"
                ),
            },
        },
    }


def compare_resolver_and_ingest(
    *,
    hand,
    tracker,
    item,
):
    resolution = (
        tracker.resolve_inferred_action(
            deepcopy(item)
        )
    )

    print()
    print("resolution:", resolution)

    if not resolution["resolved"]:
        result = tracker.ingest(
            deepcopy(item)
        )

        print("ingest:", result)

        assert result is None

        return

    result = tracker.ingest(
        deepcopy(item)
    )

    print(
        "ingest:",
        None
        if result is None
        else result.to_dict(),
    )

    assert result is not None

    assert (
        result.action
        == resolution["action"]
    )

    assert (
        result.amount_bb
        == resolution["amount_bb"]
    )

    assert (
        result.raise_to_bb
        == resolution["raise_to_bb"]
    )


def test_opening_bet_matches():
    hand = make_hand()

    hand.players_to_act = [
        "hero",
        "villain",
    ]

    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["hero", "villain"],
    )

    compare_resolver_and_ingest(
        hand=hand,
        tracker=tracker,
        item=event(
            201,
            "hero",
            "BET_OR_RAISE",
            2.5,
        ),
    )

    print(
        "PASS: opening BET resolver "
        "matches ingest"
    )


def test_exact_call_matches():
    hand = make_hand()

    hand.current_bet_bb = 3.0

    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    hand.players_to_act = [
        "hero",
        "villain",
    ]

    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["hero", "villain"],
    )

    compare_resolver_and_ingest(
        hand=hand,
        tracker=tracker,
        item=event(
            202,
            "hero",
            "CALL_OR_RAISE",
            2.0,
        ),
    )

    print(
        "PASS: exact CALL resolver "
        "matches ingest"
    )


def test_raise_matches():
    hand = make_hand()

    hand.current_bet_bb = 2.0

    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    hand.players_to_act = [
        "hero",
        "villain",
    ]

    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["hero", "villain"],
    )

    compare_resolver_and_ingest(
        hand=hand,
        tracker=tracker,
        item=event(
            203,
            "hero",
            "BET_OR_RAISE",
            5.0,
        ),
    )

    print(
        "PASS: RAISE resolver "
        "matches ingest"
    )


def test_deferred_chronology_matches():
    hand = make_hand()

    hand.players_to_act = [
        "villain",
        "hero",
    ]

    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["villain", "hero"],
    )

    item = event(
        204,
        "hero",
        "BET_OR_RAISE",
        3.0,
    )

    resolution = (
        tracker.resolve_inferred_action(
            deepcopy(item)
        )
    )

    assert resolution["resolved"] is False
    assert resolution["earlier_seats"] == [
        "villain",
    ]

    before_queue = (
        tracker.commitment_tracker
        .players_owing_action(
            "PREFLOP"
        )
    )

    result = tracker.ingest(
        deepcopy(item)
    )

    after_queue = (
        tracker.commitment_tracker
        .players_owing_action(
            "PREFLOP"
        )
    )

    assert result is None
    assert after_queue == before_queue

    print(
        "PASS: chronology-deferred resolver "
        "matches ingest"
    )


def main():
    test_opening_bet_matches()
    test_exact_call_matches()
    test_raise_matches()
    test_deferred_chronology_matches()

    print()
    print(
        "PASS BettingRoundTracker resolver / "
        "ingest semantic equivalence"
    )


if __name__ == "__main__":
    main()
