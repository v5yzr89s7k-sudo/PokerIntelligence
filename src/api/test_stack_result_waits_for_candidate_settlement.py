from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"

SAMPLE_TS = 18.891
LAST_CHANGE_TS = 19.232

FRAME52_TS = 19.568
VISUAL_SETTLE_TS = LAST_CHANGE_TS + 0.45

REQUEST_ID = "bb-frame50"


def result_row():
    return {
        "type": "stack_result",
        "request_id": REQUEST_ID,
        "hand_token": "hand-1",
        "seat": SEAT,
        "street": "PREFLOP",
        "frame": "/tmp/0050_full.png",
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": 48.57,
            "stack_text": "48.57 BB",
            "confidence": 0.50,
            "votes": 1,
            "mode": "segmentation_disagreement",
            "raw": [],
        },
        "independent": {
            "stack_bb": 48.87,
            "stack_text": "48.87 BB",
            "confidence": 0.98,
            "votes": 3,
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
            "first_change_ts": 17.855,
            "last_change_ts": LAST_CHANGE_TS,
            "last_stack_sample_ts": SAMPLE_TS,
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "stack_worker_request_id": REQUEST_ID,
        }
    }

    state["pending_stack_worker_requests"] = {
        REQUEST_ID: {
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0050_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
            "queued_ts": 0.0,
        }
    }

    return state


def main():
    old_results = c.STACK_RESULTS

    with TemporaryDirectory() as tmp:
        try:
            c.STACK_RESULTS = (
                Path(tmp)
                / "stack_results.jsonl"
            )

            c.append_jsonl(
                c.STACK_RESULTS,
                result_row(),
            )

            replay_records = [
                {
                    "index": 50,
                    "ts": SAMPLE_TS,
                    "frame_path": Path(
                        "/tmp/0050_full.png"
                    ),
                },
                {
                    "index": 51,
                    "ts": LAST_CHANGE_TS,
                    "frame_path": Path(
                        "/tmp/0051_full.png"
                    ),
                },
                {
                    "index": 52,
                    "ts": FRAME52_TS,
                    "frame_path": Path(
                        "/tmp/0052_full.png"
                    ),
                },
                {
                    "index": 53,
                    "ts": VISUAL_SETTLE_TS + 0.01,
                    "frame_path": Path(
                        "/tmp/0053_full.png"
                    ),
                },
            ]

            state = make_state()

            # Frame 52 satisfies sample settlement:
            #
            #   19.568 - 18.891 = 0.677 >= 0.45
            #
            # but does NOT satisfy candidate settlement:
            #
            #   19.568 - 19.232 = 0.336 < 0.45
            #
            # The completed result must therefore remain
            # transport-owned.
            early = (
                c.collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=FRAME52_TS,
                    replay_records=replay_records,
                )
            )

            print("frame52 ready:", early)
            print(
                "frame52 transport owned:",
                REQUEST_ID
                in state[
                    "pending_stack_worker_requests"
                ],
            )

            assert SEAT not in early, (
                "REPRODUCED: collector released completed "
                "stack result before candidate itself was "
                "visually settled"
            )

            assert (
                REQUEST_ID
                in state[
                    "pending_stack_worker_requests"
                ]
            ), (
                "REPRODUCED: completed result lost durable "
                "transport ownership before processor could "
                "legally consume it"
            )

            # Once candidate settlement has elapsed,
            # the exact same completed result becomes ready.
            late_ts = VISUAL_SETTLE_TS + 0.01

            late = (
                c.collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=late_ts,
                    replay_records=replay_records,
                )
            )

            print("late ready seats:", sorted(late))

            assert SEAT in late, late

            assert (
                REQUEST_ID
                not in state[
                    "pending_stack_worker_requests"
                ]
            )

            print(
                "PASS stack result waits for both "
                "sample settlement and candidate settlement"
            )

        finally:
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
