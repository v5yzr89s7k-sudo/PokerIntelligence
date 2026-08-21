from pathlib import Path
from tempfile import TemporaryDirectory
import json

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"

# Synthetic version of the July 22 PREFLOP ownership race.
#
# Request sampled frame 52. The worker may physically finish early or late,
# but replay semantics must expose that result on one deterministic recorded
# frame.
FRAME_TS = {
    52: 1784748140.000,
    53: 1784748140.340,
    54: 1784748140.680,
    55: 1784748141.020,
}

SAMPLE_TS = FRAME_TS[52]
RELEASE_DEADLINE = SAMPLE_TS + 0.45

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

# First recorded frame at or after sample + 0.45.
EXPECTED_RELEASE_FRAME = 54
EXPECTED_RELEASE_TS = FRAME_TS[
    EXPECTED_RELEASE_FRAME
]


def result_row(request_id):
    return {
        "type": "stack_result",
        "request_id": request_id,
        "hand_token": "hand-1",
        "seat": SEAT,
        "street": "PREFLOP",
        "frame": "/tmp/0052_full.png",
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": 47.57,
            "stack_text": "47.57 BB",
            "confidence": 0.98,
            "votes": 3,
            "mode": "agreement_verified",
            "raw": [],
        },
        "independent": {
            "stack_bb": 47.57,
            "stack_text": "47.57 BB",
            "confidence": 0.98,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        },
    }


def make_state():
    state = c.fresh_state()
    state["hand_token"] = "hand-1"
    state["phase"] = "PREFLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": FRAME_TS[52] - 1.0,
            "last_change_ts": FRAME_TS[52] - 1.0,
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "bet_region_appeared",
            ],
            "stack_worker_request_id": "request-1",
            "last_stack_sample_ts": SAMPLE_TS,
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


def run_case(result_available_frame):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_results = c.STACK_RESULTS

        try:
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            state = make_state()

            observations = []

            for frame in (53, 54, 55):
                if frame == result_available_frame:
                    c.append_jsonl(
                        c.STACK_RESULTS,
                        result_row("request-1"),
                    )

                ready = (
                    c.collect_ready_stack_worker_results(
                        state,
                        replay_frame_ts=FRAME_TS[frame],
                        replay_records=REPLAY_RECORDS,
                    )
                )

                observations.append({
                    "frame": frame,
                    "ready": SEAT in ready,
                    "pending": (
                        "request-1"
                        in state[
                            "pending_stack_worker_requests"
                        ]
                    ),
                })

            return observations

        finally:
            c.STACK_RESULTS = old_results


def first_ready(observations):
    for item in observations:
        if item["ready"]:
            return item["frame"]

    return None


def main():
    # Physical result exists before semantic release.
    early = run_case(
        result_available_frame=53
    )

    # Physical result appears exactly at semantic release.
    on_time = run_case(
        result_available_frame=54
    )

    print("release deadline:", RELEASE_DEADLINE)
    print(
        "expected release:",
        EXPECTED_RELEASE_FRAME,
        EXPECTED_RELEASE_TS,
    )
    print("early :", early)
    print("on_time:", on_time)

    early_release = first_ready(early)
    on_time_release = first_ready(on_time)

    assert early_release == EXPECTED_RELEASE_FRAME, (
        "REPRODUCED: early worker completion became "
        "semantically visible before deterministic "
        f"release frame; got={early_release} "
        f"expected={EXPECTED_RELEASE_FRAME}"
    )

    assert (
        on_time_release
        == EXPECTED_RELEASE_FRAME
    ), (
        "REPRODUCED: on-time worker completion did "
        "not release at deterministic frame"
    )

    assert early_release == on_time_release

    # Before release, ownership must remain pending even though the physical
    # result file already exists.
    assert early[0] == {
        "frame": 53,
        "ready": False,
        "pending": True,
    }, early[0]

    # At release the result becomes ready and transport ownership is consumed.
    assert early[1] == {
        "frame": 54,
        "ready": True,
        "pending": False,
    }, early[1]

    print(
        "PASS stack result semantic release: "
        "worker wall-clock completion cannot choose "
        "the replay frame that mutates candidate ownership"
    )


if __name__ == "__main__":
    main()
