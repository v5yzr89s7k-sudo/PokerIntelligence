"""
Regression contract:

A prerecorded replay may release later frames before an asynchronous
settled-stack read from an earlier frame completes.

BB ground-truth case:
    baseline      = 48.57
    request frame = 0050 -> 48.57 unchanged
    frame 0051    = 47.57
    frame 0052    = 47.57

If the frame-0050 result becomes visible only during EOF drain, the
physical stack candidate must remain owned and EOF processing must
progress to eligible prerecorded evidence rather than strand the
candidate forever.

This test intentionally targets lifecycle/retry progression only.
"""

from pathlib import Path
import inspect

import src.api.api_event_coordinator as c


def main():
    source = inspect.getsource(
        c.drain_replay_stack_candidates_once
    )

    required = (
        "final_frame_path",
        "final_frame_ts",
        "replay_records",
        "process_stack_change_measurements_async",
    )

    for token in required:
        assert token in source, (
            f"EOF drain missing required transport: {token}"
        )

    records = [
        {
            "frame_path": Path("/tmp/0050_full.png"),
            "ts": 18.891,
            "stack_bb": 48.57,
        },
        {
            "frame_path": Path("/tmp/0051_full.png"),
            "ts": 19.232,
            "stack_bb": 47.57,
        },
        {
            "frame_path": Path("/tmp/0052_full.png"),
            "ts": 19.568,
            "stack_bb": 47.57,
        },
    ]

    first_result_ts = records[0]["ts"]

    # Same semantic retry rule already proven by the normal retry
    # contracts: after an unchanged physical candidate, choose the
    # first prerecorded frame at/after the retry deadline.
    #
    # Use the real production constant if exposed. Otherwise this
    # contract only proves that later prerecorded evidence exists;
    # the next gate will exercise the actual drain function.
    delay = getattr(
        c,
        "STACK_RETRY_DELAY_SECONDS",
        None,
    )

    if delay is None:
        delay = getattr(
            c,
            "STACK_SETTLE_RETRY_SECONDS",
            None,
        )

    if delay is None:
        print(
            "INFO: retry-delay constant not exposed by expected names"
        )
        eligible = records[1:]
    else:
        retry_not_before = first_result_ts + float(delay)
        eligible = [
            row
            for row in records
            if row["ts"] >= retry_not_before
        ]

    assert eligible, (
        "no later prerecorded BB frame is eligible at EOF"
    )

    target = eligible[0]

    assert target["frame_path"].name in {
        "0051_full.png",
        "0052_full.png",
    }, target

    assert target["stack_bb"] == 47.57, target

    # The defect established by Gate 2P:
    # EOF has all information necessary to progress this candidate,
    # but drain_replay_stack_candidates_once has no explicit retry
    # progression loop.
    #
    # Keep this assertion red until production behavior is repaired.
    has_retry_progression = (
        "retry_not_before_ts" in source
        or "retry_frame_path" in source
    )

    assert has_retry_progression, (
        "REGRESSION REPRODUCED: late unchanged BB result reaches EOF "
        "with valid later prerecorded 47.57 evidence available, but "
        "EOF drain has no explicit candidate retry progression"
    )

    print(
        "PASS BB EOF late-unchanged retry contract: "
        "candidate can progress to prerecorded 47.57 evidence"
    )


if __name__ == "__main__":
    main()
