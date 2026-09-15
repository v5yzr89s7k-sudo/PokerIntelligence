from src.state.action_timeline import (
    observe_action,
    refine_action,
    active_actions,
)


def base_state():
    return {
        "hand_token": "single-owner-gateway",
        "action_timeline": [],
    }


def test_second_source_cannot_create_competing_action():
    state = base_state()

    state = observe_action(
        state,
        hand_token=state["hand_token"],
        street="PREFLOP",
        seat="hero",
        action="BET_OR_RAISE",
        ts=10.0,
        source="bet_region_appeared",
        confidence=0.70,
        evidence=["bet_region_appeared"],
    )

    state = observe_action(
        state,
        hand_token=state["hand_token"],
        street="PREFLOP",
        seat="hero",
        action="FOLD",
        ts=12.0,
        source="board_boundary_action_order",
        confidence=0.90,
        evidence=["confirmed_next_street"],
    )

    actions = active_actions(
        state,
        hand_token=state["hand_token"],
    )

    assert len(actions) == 1, actions

    action = actions[0]

    assert action["action"] == "BET_OR_RAISE", action
    assert action["source"] == "bet_region_appeared", action

    print(
        "PASS: later boundary source cannot create "
        "a competing semantic action"
    )


def test_quantitative_evidence_refines_existing_owner():
    state = base_state()

    state = observe_action(
        state,
        hand_token=state["hand_token"],
        street="PREFLOP",
        seat="hero",
        action="BET_OR_RAISE",
        ts=10.0,
        source="bet_region_appeared",
        confidence=0.70,
        evidence=["bet_region_appeared"],
    )

    state = refine_action(
        state,
        hand_token=state["hand_token"],
        street="PREFLOP",
        seat="hero",
        action="RAISE",
        raise_to_bb=7.0,
        ts=11.0,
        source="settled_stack_transition",
        confidence=0.95,
        evidence=["stack_delta"],
        confirmed=True,
    )

    actions = active_actions(
        state,
        hand_token=state["hand_token"],
    )

    assert len(actions) == 1, actions

    action = actions[0]

    assert action["action"] == "RAISE", action
    assert action["raise_to_bb"] == 7.0, action
    assert action["status"] == "CONFIRMED", action

    print(
        "PASS: quantitative evidence refines "
        "the existing action owner in place"
    )


def test_same_seat_different_streets_are_distinct_actions():
    state = base_state()

    state = observe_action(
        state,
        hand_token=state["hand_token"],
        street="PREFLOP",
        seat="hero",
        action="CALL",
        ts=10.0,
        source="physical",
    )

    state = observe_action(
        state,
        hand_token=state["hand_token"],
        street="FLOP",
        seat="hero",
        action="BET",
        ts=20.0,
        source="physical",
    )

    actions = active_actions(
        state,
        hand_token=state["hand_token"],
    )

    assert len(actions) == 2, actions

    keys = {
        (a["street"], a["seat"])
        for a in actions
    }

    assert keys == {
        ("PREFLOP", "hero"),
        ("FLOP", "hero"),
    }, actions

    print(
        "PASS: ownership key remains "
        "(hand, street, seat)"
    )


def main():
    tests = [
        test_second_source_cannot_create_competing_action,
        test_quantitative_evidence_refines_existing_owner,
        test_same_seat_different_streets_are_distinct_actions,
    ]

    for test in tests:
        test()

    print(
        "PASS action timeline single-owner gateway baseline contract"
    )


if __name__ == "__main__":
    main()
