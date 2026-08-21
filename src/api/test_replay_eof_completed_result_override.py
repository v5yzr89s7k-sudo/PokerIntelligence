from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"
REQUEST_ID = "bb-request-50"

FRAME50_TS = 18.891
LAST_CHANGE_TS = 19.232
FRAME52_TS = 19.568


def main():
    old_results = c.STACK_RESULTS

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        try:
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            state = c.fresh_state()
            state["hand_token"] = "hand-1"
            state["phase"] = "PREFLOP"

            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": 17.855,
                    "last_change_ts": LAST_CHANGE_TS,
                    "last_stack_sample_ts": FRAME50_TS,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "stack_worker_request_id": (
                        REQUEST_ID
                    ),
                    "validation_attempts": 0,
                }
            }

            state[
                "pending_stack_worker_requests"
            ] = {
                REQUEST_ID: {
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "frame": "/tmp/0050_full.png",
                    "purpose": "settled",
                    "hand_token": "hand-1",
                    "queued_ts": 0.0,
                }
            }

            replay_records = [
                {
                    "index": 50,
                    "ts": FRAME50_TS,
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
            ]

            c.append_jsonl(
                c.STACK_RESULTS,
                {
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
                        "confidence": 0.98,
                        "votes": 3,
                        "mode": "test",
                        "raw": [],
                    },
                    "independent": {},
                    "error": None,
                    "elapsed_ms": 1.0,
                },
            )

            ordinary = (
                c.collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=FRAME52_TS,
                    replay_records=replay_records,
                )
            )

            print(
                "ordinary ready:",
                sorted(ordinary),
            )

            print(
                "ordinary transport owned:",
                REQUEST_ID
                in state[
                    "pending_stack_worker_requests"
                ],
            )

            assert SEAT not in ordinary
            assert (
                REQUEST_ID
                in state[
                    "pending_stack_worker_requests"
                ]
            )

            print(
                "PASS: ordinary replay correctly "
                "refuses pre-deadline release"
            )

            # EOF has now exhausted all recorded perception.
            # The worker result is physically complete and the
            # semantic candidate still owns this exact request.
            #
            # EOF must have an explicit mechanism for handing
            # that finite completed result to the processor
            # without weakening ordinary replay timing.
            eof_ready = (
                c.collect_ready_stack_worker_results(
                    state,
                    replay_frame_ts=FRAME52_TS,
                    replay_records=replay_records,
                    replay_eof=True,
                )
            )

            print(
                "EOF ready:",
                sorted(eof_ready),
            )

            assert SEAT in eof_ready, (
                "REPRODUCED: EOF has no explicit "
                "completed-result release mechanism "
                "when no later recorded semantic "
                "frame exists"
            )

            assert (
                REQUEST_ID
                not in state[
                    "pending_stack_worker_requests"
                ]
            ), (
                "REPRODUCED: EOF completed result "
                "remains transport-owned after "
                "explicit EOF release"
            )

            print(
                "PASS replay EOF completed-result "
                "override contract"
            )

        finally:
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
