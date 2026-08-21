from src.api import api_event_state_machine as sm


def make_result():
    return {
        "type": "boundary_stack_result",
        "request_id": "request-1",
        "hand_token": "hand-1",
        "street": "PREFLOP",
        "ts": 10.0,
        "observations": [
            {
                "seat": "utg",
                "observation": {
                    "stack_bb": 47.57,
                    "confidence": 0.98,
                    "votes": 4,
                    "mode": "independent",
                    "frame_ts": 9.0,
                },
            },
            {
                "seat": "sb",
                "observation": {
                    "stack_bb": 56.55,
                    "confidence": 0.98,
                    "votes": 4,
                    "mode": "independent",
                    "frame_ts": 9.0,
                },
            },
        ],
    }


def main():
    state = sm.default_state()

    result = make_result()

    state = sm.preserve_boundary_evidence(
        state,
        result,
    )

    key = "hand-1:PREFLOP"

    assert key in state[
        "preserved_boundary_evidence"
    ]

    stored = state[
        "preserved_boundary_evidence"
    ][key]

    assert set(
        stored["observations_by_seat"]
    ) == {"utg", "sb"}

    # A later result may add/refresh evidence without deleting the first set.
    later = make_result()
    later["request_id"] = "request-2"
    later["observations"] = [
        {
            "seat": "hero",
            "observation": {
                "stack_bb": 10.28,
                "confidence": 0.98,
                "votes": 5,
                "mode": "independent",
                "frame_ts": 9.5,
            },
        },
    ]

    state = sm.preserve_boundary_evidence(
        state,
        later,
    )

    stored = state[
        "preserved_boundary_evidence"
    ][key]

    assert set(
        stored["observations_by_seat"]
    ) == {
        "utg",
        "sb",
        "hero",
    }

    state = sm.clear_preserved_boundary_evidence(
        state,
        hand_token="hand-1",
        street="PREFLOP",
    )

    assert key not in state[
        "preserved_boundary_evidence"
    ]

    print(
        "PASS preserved boundary evidence: "
        "unresolved old-street observations survive "
        "one-shot result handling and clear explicitly"
    )


if __name__ == "__main__":
    main()
