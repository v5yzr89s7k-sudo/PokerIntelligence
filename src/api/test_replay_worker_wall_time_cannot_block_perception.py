"""
Regression contract:

Recorded replay chronology is deterministic in semantic time, but asynchronous
worker wall-clock completion must never control admission of the next recorded
frame into perception.

This test is intentionally RED against the current barrier architecture.
"""

from unittest.mock import patch
import os

import src.api.api_event_coordinator as c


def main():
    request_id = "slow-stack-request"

    state = {
        "pending_stack_worker_requests": {
            request_id: {
                "request_id": request_id,
                "seat": "seat_lower_left",
                "street": "TURN",
                "purpose": "settled",
                "frame": "/tmp/0100_full.png",
                "hand_token": "wall-time-contract",
            },
        },
        "pending_stack_reads": {
            "seat_lower_left": {
                "hand_token": "wall-time-contract",
                "origin_street": "TURN",
                "stack_worker_request_id": request_id,
                "last_stack_sample_ts": 100.0,
                "last_change_ts": 100.0,
            },
        },
    }

    replay_records = [
        {
            "index": 100,
            "ts": 100.0,
            "frame_path": "/tmp/0100_full.png",
        },
        {
            "index": 101,
            "ts": 100.2,
            "frame_path": "/tmp/0101_full.png",
        },
        {
            "index": 102,
            "ts": 100.5,
            "frame_path": "/tmp/0102_full.png",
        },
        {
            "index": 103,
            "ts": 101.0,
            "frame_path": "/tmp/0103_full.png",
        },
    ]

    release_ts = c._replay_stack_request_release_ts(
        state,
        request_id,
        state["pending_stack_worker_requests"][request_id],
        replay_records,
    )

    print("semantic release:", release_ts)

    assert release_ts == 100.5, (
        "fixture error: expected semantic release at frame 102"
    )

    # Worker is deliberately still physically unavailable.
    with patch.dict(
        os.environ,
        {
            "POKER_REPLAY_FAST": "1",
        },
        clear=False,
    ), patch.object(
        c,
        "find_stack_worker_result",
        return_value=None,
    ):
        current_allows = (
            c.replay_stack_semantic_barrier_allows_advance(
                state,
                next_frame_ts=100.5,
                replay_records=replay_records,
            )
        )

    print(
        "perception advance at semantic release:",
        current_allows,
    )

    # NEW architecture contract:
    #
    # Semantic release time controls when the result MAY affect state.
    # It must not control whether subsequent recorded frames may enter
    # LocalEventDetector merely because physical computation is late.
    assert current_allows is True, (
        "RED: asynchronous stack-worker wall time still owns "
        "recorded perception advancement"
    )

    print(
        "PASS: recorded perception advances independently of "
        "asynchronous worker wall-clock completion"
    )


if __name__ == "__main__":
    main()
