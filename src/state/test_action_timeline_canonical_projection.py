from src.state.action_timeline import (
    active_actions,
    observe_action,
    project_action_to_canonical,
)
from src.state.canonical_hand import CanonicalHand


TOKEN = "canonical-projection-test"
SEAT = "hero"


def make_hand():
    return CanonicalHand().start_hand(
        hand_id=TOKEN,
        players=[
            {
                "seat": SEAT,
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
            SEAT: "BTN",
            "villain": "BB",
        },
        started_ts=1.0,
    )


def base_state():
    return {
        "hand_token": TOKEN,
        "action_timeline": [],
    }


def voluntary_actions(hand):
    return [
        action
        for action in hand.actions
        if action.action.upper()
        not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]


def test_missing_owner_cannot_materialize():
    state = base_state()
    hand = make_hand()

    before = list(voluntary_actions(hand))

    result = project_action_to_canonical(
        state,
        hand=hand,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
    )

    after = list(voluntary_actions(hand))

    assert result is None
    assert before == after

    print(
        "PASS: no timeline owner means no "
        "canonical action can be invented"
    )


def test_existing_owner_materializes_once():
    state = base_state()
    hand = make_hand()

    state = observe_action(
        state,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
        action="FOLD",
        ts=10.0,
        source="trusted_boundary_stack",
        confidence=0.98,
        evidence=[
            "trusted_terminal_stack",
            "preserved_action_obligation",
        ],
    )

    first = project_action_to_canonical(
        state,
        hand=hand,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
    )

    actions = voluntary_actions(hand)

    assert first is not None
    assert len(actions) == 1
    assert actions[0].seat == SEAT
    assert actions[0].street == "PREFLOP"
    assert actions[0].action == "FOLD"

    second = project_action_to_canonical(
        state,
        hand=hand,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
    )

    actions = voluntary_actions(hand)

    assert len(actions) == 1, (
        "projection duplicated the canonical action"
    )

    assert second is actions[0] or second is None

    print(
        "PASS: durable owner materializes exactly once"
    )


def test_projection_preserves_owner_identity():
    state = base_state()
    hand = make_hand()

    state = observe_action(
        state,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
        action="CALL",
        ts=20.0,
        source="boundary_stack_resolution",
        confidence=0.98,
        evidence=[
            "trusted_terminal_stack",
        ],
    )

    item = active_actions(
        state,
        hand_token=TOKEN,
    )[0]

    item["amount_bb"] = 1.0

    # active_actions() returns a copy, so enrich the real owner
    # through the public refinement gateway.
    from src.state.action_timeline import refine_action

    state = refine_action(
        state,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
        action="CALL",
        amount_bb=1.0,
        ts=20.0,
        source="boundary_stack_resolution",
        confidence=0.98,
        evidence=[
            "trusted_terminal_stack",
        ],
        confirmed=True,
    )

    projected = project_action_to_canonical(
        state,
        hand=hand,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
    )

    assert projected is not None
    assert projected.seat == SEAT
    assert projected.street == "PREFLOP"
    assert projected.action == "CALL"
    assert projected.amount_bb == 1.0

    owner = active_actions(
        state,
        hand_token=TOKEN,
    )[0]

    assert owner["seat"] == projected.seat
    assert owner["street"] == projected.street
    assert owner["action"] == projected.action

    print(
        "PASS: canonical materialization projects "
        "the existing owner rather than redefining it"
    )


def main():
    tests = [
        test_missing_owner_cannot_materialize,
        test_existing_owner_materializes_once,
        test_projection_preserves_owner_identity,
    ]

    for test in tests:
        test()

    print(
        "PASS ActionTimeline canonical projection "
        "gateway contract"
    )


if __name__ == "__main__":
    main()
