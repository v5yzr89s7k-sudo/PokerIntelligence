from types import SimpleNamespace

import src.api.api_event_state_machine as sm
from src.state.action_timeline import (
    active_actions,
    observe_action,
)


TOKEN = "canonical-refines-single-owner"
SEAT = "seat_utg"


def main():
    state = sm.default_state()

    state["hand_token"] = TOKEN
    state["phase"] = "PREFLOP"

    state = observe_action(
        state,
        hand_token=TOKEN,
        street="PREFLOP",
        seat=SEAT,
        action="BET_OR_RAISE",
        ts=1.0,
        source="bet_region_appeared",
        confidence=0.7,
        evidence=["bet_region_appeared"],
    )

    before = active_actions(
        state,
        TOKEN,
    )

    print("===== BEFORE CANONICAL SETTLEMENT =====")
    print(before)

    assert len(before) == 1
    assert before[0]["action"] == "BET_OR_RAISE"
    assert before[0]["amount_bb"] is None

    canonical_action = SimpleNamespace(
        street="PREFLOP",
        seat=SEAT,
        action="RAISE",
        amount_bb=None,
        raise_to_bb=2.2,
        ts=1.4,
        source="settled_stack_transition",
        confidence=0.95,
    )

    state = sm.refine_action_timeline_from_canonical(
        state,
        canonical_action,
    )

    after = active_actions(
        state,
        TOKEN,
    )

    print()
    print("===== AFTER CANONICAL SETTLEMENT =====")
    print(after)

    assert len(after) == 1, (
        "canonical settlement created competing action ownership"
    )

    action = after[0]

    assert action["action"] == "RAISE"
    assert action["raise_to_bb"] == 2.2
    assert action["status"] == "CONFIRMED"

    assert action["first_observed_ts"] == 1.0, (
        "canonical settlement replaced original physical onset time"
    )

    assert "bet_region_appeared" in action["evidence"]
    assert "canonical_settlement" in action["evidence"]

    print()
    print(
        "PASS: canonical settlement refines the original durable "
        "physical action instead of creating a second owner"
    )


if __name__ == "__main__":
    main()
