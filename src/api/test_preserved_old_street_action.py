from src.api import api_event_state_machine as sm


def main():
    state = sm.default_state()

    state["hand_token"] = "hand-1"

    key = "hand-1:PREFLOP"

    state["preserved_boundary_evidence"] = {
        key: {
            "hand_token": "hand-1",
            "street": "PREFLOP",
            "observations_by_seat": {},
        }
    }

    first = {
        "type": "inferred_action",
        "episode_id": 4,
        "street": "PREFLOP",
        "seat": "utg",
        "action": "CALL_OR_RAISE",
        "delta_bb": 1.0,
        "confidence": 0.80,
        "ts": 10.0,
    }

    state = sm.preserve_old_street_inferred_action(
        state,
        first,
    )

    stored = state[
        "preserved_inferred_actions"
    ][key]["actions_by_seat"]

    assert stored["utg"]["delta_bb"] == 1.0

    # Stronger later evidence replaces weaker evidence for the same seat.
    stronger = dict(first)
    stronger["confidence"] = 0.98
    stronger["ts"] = 11.0

    state = sm.preserve_old_street_inferred_action(
        state,
        stronger,
    )

    stored = state[
        "preserved_inferred_actions"
    ][key]["actions_by_seat"]

    assert stored["utg"]["confidence"] == 0.98

    state = sm.clear_preserved_inferred_actions(
        state,
        hand_token="hand-1",
        street="PREFLOP",
    )

    assert key not in state[
        "preserved_inferred_actions"
    ]

    print(
        "PASS preserved old-street inferred action: "
        "qualified stale evidence is retained separately "
        "and cleared explicitly"
    )


if __name__ == "__main__":
    main()
