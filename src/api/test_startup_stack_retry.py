from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as coord


def main():
    state = coord.fresh_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = "test-hand"
    state["pending_startup_stack_seats"] = [
        "seat_lower_right",
        "seat_lower_left",
    ]

    image = np.zeros((696, 934, 3), dtype=np.uint8)
    emitted = []

    with (
        patch.object(
            coord,
            "_canonical_stack_values",
            return_value={},
        ),
        patch.object(
            coord,
            "prechange_stack_observation",
            side_effect=[
                {
                    "observed_stack_bb": 58.55,
                    "confidence": 0.98,
                    "votes": 5,
                    "mode": "independent_segmentation",
                },
                {
                    "observed_stack_bb": 48.57,
                    "confidence": 0.98,
                    "votes": 3,
                    "mode": "independent_segmentation",
                },
            ],
        ),
        patch.object(
            coord,
            "emit",
            side_effect=lambda event: emitted.append(event),
        ),
        patch.object(
            coord.time,
            "time",
            side_effect=[10.0, 10.30],
        ),
    ):
        state = coord.retry_one_startup_stack(
            state,
            image,
            local_board_count=0,
        )

        assert state["pending_startup_stack_seats"] == [
            "seat_lower_left"
        ]

        state = coord.retry_one_startup_stack(
            state,
            image,
            local_board_count=0,
        )

    assert state["pending_startup_stack_seats"] == []

    assert [
        event["seat"]
        for event in emitted
    ] == [
        "seat_lower_right",
        "seat_lower_left",
    ]

    assert emitted[0]["observed_stack_bb"] == 58.55
    assert emitted[1]["observed_stack_bb"] == 48.57

    assert all(
        event["type"] == "stack_baseline_observation"
        for event in emitted
    )

    assert all(
        event["source"] == "startup_retry"
        for event in emitted
    )

    print(
        "PASS startup stack retry: ambiguous bootstrap "
        "stacks resolve incrementally without stack motion"
    )


if __name__ == "__main__":
    main()
