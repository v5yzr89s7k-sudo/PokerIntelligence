from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)


def make_hand():
    players = [
        {
            "seat": "seat_top",
            "name": "P1",
            "stack_bb": 100,
        },
        {
            "seat": "seat_upper_right",
            "name": "P2",
            "stack_bb": 100,
        },
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 100,
        },
    ]

    positions = {
        "seat_top": "UTG",
        "seat_upper_right": "HJ",
        "hero": "BTN",
    }

    hand = CanonicalHand().start_hand(
        hand_id="deferred-cross-street",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions=positions,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(positions)

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # First actor establishes a real voluntary commitment.
    first = tracker.ingest({
        "episode_id": 1,
        "seat": "seat_top",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.0,
            },
            "table_context": {
                "prior_voluntary_commitment_seats": [],
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    assert first is not None

    # Preserve objective commitment evidence for the skipped HJ seat.
    tracker.commitment_tracker.record_commitment(
        "PREFLOP",
        "seat_upper_right",
    )

    deferred_event = {
        "episode_id": 2,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "CALL_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.0,
            },
            "table_context": {
                "prior_voluntary_commitment_seats": [
                    "seat_top",
                    "seat_upper_right",
                ],
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 3.0,
    }

    deferred = tracker.ingest(deferred_event)

    assert deferred is None

    decision = tracker.decisions[-1]

    assert "deferred" in decision.reason.lower(), decision
    assert 2 not in tracker.processed_episode_ids

    preflop_before = (
        tracker.commitment_tracker.to_dict()["PREFLOP"]
    )

    print("===== DEFERRED ON PREFLOP =====")
    print(decision)
    print(preflop_before)

    # Advance the canonical hand normally. We are deliberately NOT resolving
    # the deferred event here.
    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=4.0,
    )

    assert hand.current_street == "FLOP"

    # Force tracker street synchronization.
    tracker._sync_street()

    states = tracker.commitment_tracker.to_dict()

    assert "PREFLOP" in states
    assert "FLOP" in states

    preflop_after = states["PREFLOP"]

    assert (
        preflop_after["committed"]
        == preflop_before["committed"]
    )

    assert (
        preflop_after["street_order"]
        == preflop_before["street_order"]
    )

    print()
    print("===== PREFLOP STATE SURVIVES FLOP =====")
    print(preflop_after)

    actions_before_retry = [
        action.to_dict()
        for action in hand.actions
    ]

    retried = tracker.ingest(deferred_event)

    assert retried is None

    stale_decision = tracker.decisions[-1]

    assert (
        stale_decision.reason
        == "action street does not match canonical hand street"
    ), stale_decision

    # Critical safety invariant: normal stale replay must not manufacture
    # a FLOP action from PREFLOP evidence.
    actions_after_retry = [
        action.to_dict()
        for action in hand.actions
    ]

    assert actions_after_retry == actions_before_retry

    assert not any(
        action.street == "FLOP"
        and action.seat == "hero"
        for action in hand.actions
    )

    print()
    print("===== NORMAL RETRY AFTER FLOP =====")
    print(stale_decision)

    print()
    print(
        "PASS deferred cross-street contract: "
        "PREFLOP evidence survives; normal ingest rejects stale replay; "
        "no false FLOP action is created"
    )


if __name__ == "__main__":
    main()
