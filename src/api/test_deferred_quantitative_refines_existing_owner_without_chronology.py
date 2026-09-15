from copy import deepcopy

from src.state.action_timeline import (
    observe_action,
    refine_action,
    find_action,
)
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="deferred-refinement",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["Ah", "Qd"],
        hero_position="SB",
        positions={
            "utg": "UTG",
            "btn": "BTN",
            "hero": "SB",
            "bb": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0

    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 0.5

    hand.players["bb"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    hand.players_to_act = [
        "utg",
        "btn",
        "hero",
        "bb",
    ]

    return hand


def event():
    return {
        "episode_id": 202,
        "street": "PREFLOP",
        "seat": "hero",
        "action": "CALL_OR_RAISE",
        "confidence": 0.99,
        "evidence": [
            "settled_stack_transition",
        ],
        "ts": 202.0,
        "measurements": {
            "stack_change": {
                "delta_bb": 1.5,
                "stack_read_confidence": 0.99,
                "stack_read_mode": "agreement_verified",
            }
        },
    }


def voluntary_actions(hand):
    return [
        action
        for action in hand.actions
        if action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        list(hand.players_to_act),
    )

    tracker.commitment_tracker.record_pending_quantitative_commitment(
        "PREFLOP",
        "btn",
        2.0,
    )

    timeline = {}

    timeline = observe_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
        action="COMMITMENT",
        ts=200.0,
        source="bet_region_appeared",
        confidence=0.7,
        evidence=[
            "physical_commitment",
        ],
    )

    before_queue = list(
        hand.players_to_act
    )

    before_canonical_count = len(
        voluntary_actions(hand)
    )

    resolution = tracker.resolve_inferred_action(
        deepcopy(event())
    )

    print("===== RESOLUTION =====")
    print(resolution)

    assert resolution["resolved"] is False
    assert (
        resolution["reason"]
        == "earlier actors remain unresolved"
    )
    assert resolution["action"] == "CALL"

    owner_before = find_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
    )

    assert owner_before is not None
    assert (
        str(
            owner_before.get("action")
            or ""
        ).upper()
        == "COMMITMENT"
    )

    timeline = refine_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
        action="CALL",
        amount_bb=1.5,
        raise_to_bb=None,
        ts=202.0,
        source="settled_stack_transition",
        confidence=0.99,
        evidence=[
            "settled_stack_transition",
            "chronology_pending",
        ],
        confirmed=True,
    )

    owner_after = find_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
    )

    print()
    print("===== OWNER AFTER REFINEMENT =====")
    print(owner_after)

    assert owner_after is not None
    assert owner_after.get("action") == "CALL"
    assert owner_after.get("amount_bb") == 1.5

    assert (
        len(voluntary_actions(hand))
        == before_canonical_count
    )

    assert hand.players_to_act == before_queue

    assert hand.current_bet_bb == 1.0
    assert hand.last_aggressor_seat is None

    print()
    print(
        "PASS: deferred quantitative CALL refined the existing "
        "ActionTimeline owner without canonical admission "
        "or chronology consumption"
    )


if __name__ == "__main__":
    main()
