from pathlib import Path

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"

FRAME_TS = {
    52: 1784748140.000,
    53: 1784748140.340,
    54: 1784748140.680,
    55: 1784748141.020,
}

REPLAY_RECORDS = [
    {
        "index": index,
        "ts": ts,
        "frame_path": Path(
            f"/tmp/{index:04d}_full.png"
        ),
    }
    for index, ts in FRAME_TS.items()
]

SAMPLE_TS = FRAME_TS[52]


def make_state():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "PREFLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": SAMPLE_TS - 1.0,
            "last_change_ts": SAMPLE_TS - 1.0,
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "bet_region_appeared",
            ],
            "stack_worker_request_id": "request-1",
            "last_stack_sample_ts": SAMPLE_TS,
            "hand_token": "hand-1",
        },
    }

    state["pending_stack_worker_requests"] = {
        "request-1": {
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0052_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
            "queued_ts": 0.0,
        },
    }

    return state


def main():
    state = make_state()

    # Frame 53 is still before sample + 0.45.
    #
    # Replay may advance from 52 -> 53 even though the physical
    # worker result does not exist yet.
    allow_53 = c.replay_stack_semantic_barrier_allows_advance(
        state,
        next_frame_ts=FRAME_TS[53],
        replay_records=REPLAY_RECORDS,
    )

    # Frame 54 is the first recorded frame at/after the
    # deterministic settlement deadline.
    #
    # If request-1 has not physically completed, replay must NOT
    # release frame 54 into LocalEventDetector. Otherwise worker
    # wall-clock latency chooses whether ownership survives into
    # later recorded evidence.
    allow_54_without_result = (
        c.replay_stack_semantic_barrier_allows_advance(
            state,
            next_frame_ts=FRAME_TS[54],
            replay_records=REPLAY_RECORDS,
        )
    )

    print(
        "advance 52 -> 53:",
        allow_53,
    )
    print(
        "advance 53 -> 54 with unresolved worker:",
        allow_54_without_result,
    )

    assert allow_53 is True, (
        "REPRODUCED: replay barrier blocked before "
        "the deterministic semantic release frame"
    )

    assert allow_54_without_result is False, (
        "REPRODUCED: replay can cross a settled-stack "
        "semantic release boundary while the owning "
        "worker request is still unresolved"
    )

    # Simulate the worker completing late in wall time while replay is held
    # immediately before frame 54. The same next frame must become eligible
    # without changing recorded semantic time.
    old_finder = c.find_stack_worker_result

    try:
        c.find_stack_worker_result = (
            lambda request_id: {
                "request_id": request_id,
                "hand_token": "hand-1",
                "seat": SEAT,
                "street": "PREFLOP",
                "purpose": "settled",
                "ok": True,
            }
        )

        allow_54_after_result = (
            c.replay_stack_semantic_barrier_allows_advance(
                state,
                next_frame_ts=FRAME_TS[54],
                replay_records=REPLAY_RECORDS,
            )
        )

    finally:
        c.find_stack_worker_result = old_finder

    print(
        "advance 53 -> 54 after worker completes:",
        allow_54_after_result,
    )

    assert allow_54_after_result is True, (
        "REPRODUCED: replay remained blocked after "
        "the owning settled-stack result became available"
    )

    print(
        "PASS replay stack semantic barrier: "
        "replay advances normally before the release "
        "boundary and holds exactly at the first "
        "eligible recorded release frame"
    )


if __name__ == "__main__":
    main()
