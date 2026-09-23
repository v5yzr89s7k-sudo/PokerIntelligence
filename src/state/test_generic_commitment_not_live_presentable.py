from src.state.action_timeline import (
    active_actions,
    observe_action,
    presentation_overlay,
    refine_action,
)


TOKEN = "generic-commitment-presentation"
STREET = "PREFLOP"
SEAT = "hero"


def main():
    state = {
        "hand_token": TOKEN,
        "action_timeline": [],
    }

    state = observe_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        action="COMMITMENT",
        ts=1.0,
        source="physical_commitment",
        confidence=0.8,
        evidence=[
            "physical_commitment",
        ],
    )

    actions = active_actions(
        state,
        hand_token=TOKEN,
    )

    print("===== DURABLE EVIDENCE =====")
    print(actions)

    assert len(actions) == 1
    assert actions[0]["action"] == "COMMITMENT"

    overlay = presentation_overlay(
        state
    )

    print()
    print("===== GENERIC PRESENTATION =====")
    print(overlay)

    assert (
        f"{STREET}:{SEAT}"
        not in overlay
    ), (
        "RED: evidence-only COMMITMENT leaked "
        "into live presentation"
    )

    state = refine_action(
        state,
        hand_token=TOKEN,
        street=STREET,
        seat=SEAT,
        action="CALL",
        amount_bb=1.5,
        ts=2.0,
        source="settled_stack_transition",
        confidence=0.99,
        evidence=[
            "quantitative_resolution",
        ],
        confirmed=True,
    )

    actions = active_actions(
        state,
        hand_token=TOKEN,
    )

    assert len(actions) == 1
    assert actions[0]["action"] == "CALL"
    assert actions[0]["amount_bb"] == 1.5

    overlay = presentation_overlay(
        state
    )

    print()
    print("===== REFINED PRESENTATION =====")
    print(overlay)

    key = f"{STREET}:{SEAT}"

    assert key in overlay
    assert overlay[key]["action"] == "CALL"
    assert overlay[key]["amount_bb"] == 1.5

    print()
    print(
        "PASS: generic physical COMMITMENT remains durable "
        "but becomes live-presentable only after semantic refinement"
    )


if __name__ == "__main__":
    main()
