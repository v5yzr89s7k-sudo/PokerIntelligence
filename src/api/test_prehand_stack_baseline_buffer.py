from src.api import api_event_state_machine as sm


def trusted_baseline(
    seat="seat_mid_right",
    value=55.41,
    ts=100.0,
):
    return {
        "type": "stack_baseline_observation",
        "seat": seat,
        "observed_stack_bb": value,
        "confidence": 0.98,
        "votes": 5,
        "mode": "independent_segmentation",
        "origin_street": "WAITING",
        "ts": ts,
    }


def test_trusted_prehand_baseline_survives_hand_activation():
    state = sm.default_state()

    # Represents the short local-start / canonical-start race:
    # pixels already belong to the emerging hand, but Hero cards
    # have not yet transitioned canonical state to PREFLOP.
    state["hand_token"] = "emerging-hand-token"

    event = trusted_baseline()

    state = sm.handle_stack_baseline_observation(
        state,
        event,
    )

    pending = state[
        "pending_stack_baseline_observations"
    ]

    assert len(pending) == 1, pending
    assert pending[0]["seat"] == "seat_mid_right"
    assert pending[0]["observed_stack_bb"] == 55.41

    state = sm.handle_hero_cards(
        state,
        {
            "type": "hero_cards",
            "hero_cards": ["As", "Kd"],
            "ts": 101.0,
        },
    )

    assert state["phase"] == "PREFLOP"

    pending = state[
        "pending_stack_baseline_observations"
    ]

    assert len(pending) == 1, pending
    assert pending[0]["seat"] == "seat_mid_right"
    assert pending[0]["observed_stack_bb"] == 55.41

    print(
        "PASS prehand baseline preservation: "
        "trusted emerging-hand evidence survives "
        "WAITING -> PREFLOP"
    )


def test_ordinary_waiting_baseline_still_rejected():
    state = sm.default_state()

    assert not state.get("hand_token")

    state = sm.handle_stack_baseline_observation(
        state,
        trusted_baseline(),
    )

    assert (
        state["pending_stack_baseline_observations"]
        == []
    )

    print(
        "PASS waiting safety: baseline without "
        "an emerging hand token remains rejected"
    )


def main():
    test_trusted_prehand_baseline_survives_hand_activation()
    test_ordinary_waiting_baseline_still_rejected()


if __name__ == "__main__":
    main()
