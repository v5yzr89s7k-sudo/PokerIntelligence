from copy import deepcopy

from src.state.action_timeline import (
    observe_action,
    refine_action,
    project_action_to_canonical,
)
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="apply-resolved-action",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
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
    hand.current_bet_bb = 0.0
    hand.players_to_act = [
        "hero",
        "villain",
    ]

    return hand


def event():
    return {
        "episode_id": 301,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.5,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "agreement_verified",
            },
        },
        "evidence": [
            "stack_changed",
        ],
        "ts": 301.0,
    }


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    item = event()

    resolution = tracker.resolve_inferred_action(
        deepcopy(item)
    )

    assert resolution["resolved"] is True
    assert resolution["action"] == "BET"
    assert resolution["amount_bb"] == 2.5

    timeline = {}

    timeline = observe_action(
        timeline,
        hand_token=hand.hand_id,
        street=resolution["street"],
        seat=resolution["seat"],
        action=resolution["action"],
        ts=resolution["ts"],
        source="betting_round_tracker",
        confidence=resolution["confidence"],
        evidence=resolution["evidence"],
    )

    timeline = refine_action(
        timeline,
        hand_token=hand.hand_id,
        street=resolution["street"],
        seat=resolution["seat"],
        action=resolution["action"],
        amount_bb=resolution["amount_bb"],
        raise_to_bb=resolution["raise_to_bb"],
        ts=resolution["ts"],
        source="betting_round_tracker",
        confidence=resolution["confidence"],
        evidence=resolution["evidence"],
        confirmed=True,
    )

    canonical = project_action_to_canonical(
        timeline,
        hand=hand,
        hand_token=hand.hand_id,
        street=resolution["street"],
        seat=resolution["seat"],
    )

    assert canonical is not None
    assert canonical.action == "BET"
    assert canonical.amount_bb == 2.5

    assert len([
        action
        for action in hand.actions
        if action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]) == 1

    before_count = len(hand.actions)

    apply_method = getattr(
        tracker,
        "apply_resolved_action",
        None,
    )

    assert apply_method is not None, (
        "RED: BettingRoundTracker has no "
        "apply_resolved_action() application API"
    )

    result = apply_method(
        inferred_action=deepcopy(item),
        resolution=deepcopy(resolution),
        canonical=canonical,
    )

    assert result is canonical

    # Application must consume the already projected action.
    # It must never create another canonical action.
    assert len(hand.actions) == before_count

    assert tracker.has_open_bet is True
    assert tracker.last_aggressor_seat == "hero"
    assert hand.last_aggressor_seat == "hero"

    owing = (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
    )

    assert owing == ["villain"], owing

    assert 301 in tracker.processed_episode_ids

    decision = tracker.decisions[-1]

    assert decision.accepted is True
    assert decision.canonical_action == "BET"

    print(
        "PASS: BettingRoundTracker applies an "
        "ActionTimeline-projected canonical action "
        "without owning canonical mutation"
    )


if __name__ == "__main__":
    main()
