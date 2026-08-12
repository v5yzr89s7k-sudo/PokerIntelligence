from unittest.mock import patch

import src.api.api_event_coordinator as coordinator


def main():
    emitted = []

    state = coordinator.fresh_state()
    state["phase"] = "FLOP"
    state["hero_decision_active"] = True
    state["last_hero_action_complete_phase"] = None
    state["hero_clear_seen"] = 0

    def capture(event):
        emitted.append(dict(event))

    with patch.object(
        coordinator,
        "emit",
        side_effect=capture,
    ):
        # Replay 0001 frame 86:
        # Hero cards explicitly transition visible -> cleared while the
        # Hero decision is still active.
        hero_cards_cleared = True

        if (
            hero_cards_cleared
            and state.get("hero_decision_active")
        ):
            coordinator.emit({
                "type": "hero_action_complete",
            })
            state["hero_decision_active"] = False
            state["last_hero_action_complete_phase"] = (
                state.get("phase")
            )
        else:
            raise AssertionError(
                "Replay fold completion path did not activate"
            )

        assert state["hero_decision_active"] is False
        assert (
            state["last_hero_action_complete_phase"]
            == "FLOP"
        )

        # Frame 86 is the first clear frame.
        state = coordinator.maybe_complete_early(
            state,
            3,
            False,
        )

        assert state["hero_clear_seen"] == 1

        # Three more clear frames reproduce the existing four-frame
        # completion debounce.
        state = coordinator.maybe_complete_early(
            state,
            3,
            False,
        )
        state = coordinator.maybe_complete_early(
            state,
            3,
            False,
        )
        state = coordinator.maybe_complete_early(
            state,
            3,
            False,
        )

    types = [
        event.get("type")
        for event in emitted
    ]

    print("===== EMITTED =====")
    for event in emitted:
        print(event)

    assert types == [
        "hero_action_complete",
        "hero_fold",
        "hand_complete",
    ], emitted

    fold = [
        event
        for event in emitted
        if event.get("type") == "hero_fold"
    ][0]

    complete = [
        event
        for event in emitted
        if event.get("type") == "hand_complete"
    ][0]

    assert fold["street"] == "FLOP", fold
    assert (
        complete["result"]
        == "Hero folded on flop"
    ), complete

    print()
    print(
        "PASS Replay 0001 Hero fold completion: "
        "card clear completes active FLOP decision; "
        "sustained clear emits hero_fold"
    )


if __name__ == "__main__":
    main()
