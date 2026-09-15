from src.state.action_timeline import (
    observe_action,
    refine_action,
    project_action_to_canonical,
)
from src.state.canonical_hand import CanonicalHand


FORCED = {
    "POST_ANTE",
    "POST_SMALL_BLIND",
    "POST_BIG_BLIND",
}


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="timeline-voluntary-projection",
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


def main():
    hand = make_hand()

    timeline = {}

    timeline = observe_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
        action="BET",
        ts=10.0,
        source="voluntary_projection_regression",
        confidence=0.98,
        evidence=["stack_changed"],
    )

    timeline = refine_action(
        timeline,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
        action="BET",
        amount_bb=2.5,
        raise_to_bb=None,
        ts=10.0,
        source="voluntary_projection_regression",
        confidence=0.98,
        evidence=["stack_changed"],
        confirmed=True,
    )

    before = [
        action
        for action in hand.actions
        if action.action not in FORCED
    ]

    assert before == []

    projected = project_action_to_canonical(
        timeline,
        hand=hand,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
    )

    assert projected is not None
    assert projected.street == "PREFLOP"
    assert projected.seat == "hero"
    assert projected.action == "BET"
    assert projected.amount_bb == 2.5
    assert projected.raise_to_bb is None

    voluntary = [
        action
        for action in hand.actions
        if action.action not in FORCED
    ]

    assert len(voluntary) == 1
    assert voluntary[0] is projected

    # Projection must remain idempotent.
    projected_again = project_action_to_canonical(
        timeline,
        hand=hand,
        hand_token=hand.hand_id,
        street="PREFLOP",
        seat="hero",
    )

    assert projected_again is projected

    voluntary_again = [
        action
        for action in hand.actions
        if action.action not in FORCED
    ]

    assert len(voluntary_again) == 1

    print(
        "PASS: ActionTimeline projects one voluntary "
        "BET into CanonicalHand and repeated projection "
        "is idempotent"
    )


if __name__ == "__main__":
    main()
