from src.state.action_timeline import (
    active_actions,
    observe_action,
    presentation_overlay,
    refine_action,
    reject_action,
)


TOKEN = "single-owner-test"
SEAT = "hero"
STREET = "FLOP"


def fresh_state():
    return {
        "hand_token": TOKEN,
        "action_timeline": [],
    }


def main():
    state = fresh_state()

    # Physical evidence creates exactly one durable action.
    state = observe_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        action="BET",
        ts=10.0,
        source="bet_region_appeared",
        confidence=0.7,
        evidence=["bet_region_appeared"],
    )

    state = observe_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        action="BET",
        ts=10.1,
        source="bet_region_appeared",
        confidence=0.7,
        evidence=["bet_region_appeared"],
    )

    actions = active_actions(
        state,
        TOKEN,
    )

    print("after physical observation:")
    print(actions)

    assert len(actions) == 1, (
        "duplicate evidence created multiple action owners"
    )

    assert actions[0]["action"] == "BET"

    # Quantitative failure is NOT contradictory evidence.
    state = reject_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        reason="stack_candidate_uncorroborated",
        contradictory_evidence=False,
        ts=12.5,
    )

    actions = active_actions(
        state,
        TOKEN,
    )

    print()
    print("after quantitative failure:")
    print(actions)

    assert len(actions) == 1, (
        "quantitative failure erased physical action"
    )

    # Later sizing/refinement modifies the same action.
    state = refine_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        action="BET",
        amount_bb=3.5,
        ts=13.0,
        source="stack_quantitative",
        confidence=0.95,
        evidence=["stack_delta"],
        confirmed=True,
    )

    actions = active_actions(
        state,
        TOKEN,
    )

    print()
    print("after enrichment:")
    print(actions)

    assert len(actions) == 1
    assert actions[0]["amount_bb"] == 3.5
    assert actions[0]["status"] == "CONFIRMED"

    overlay = presentation_overlay(
        state
    )

    assert f"{STREET}:{SEAT}" in overlay

    # Explicit contradictory evidence may reject the record.
    state = reject_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        reason="explicit_physical_contradiction",
        contradictory_evidence=True,
        ts=14.0,
    )

    actions = active_actions(
        state,
        TOKEN,
    )

    print()
    print("after explicit contradiction:")
    print(actions)

    assert actions == []

    print()
    print(
        "PASS: one durable action owner survives enrichment "
        "failure, refines in place, and rejects only on "
        "explicit contradiction"
    )


if __name__ == "__main__":
    main()
