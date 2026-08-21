from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as c


SEAT = "seat_lower_left"

FRAME50_TS = 18.891
FRAME52_TS = 19.568

REQUEST_ID = "bb-request-50"


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
                    "last_change_ts": 19.232,
                    "last_stack_sample_ts": FRAME50_TS,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "stack_worker_request_id": REQUEST_ID,
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
                    "ts": 19.232,
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

            # Real Gate 2T first BB result:
            # frame 50 still displays the unchanged 48.57 stack.
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
                        "confidence": 0.50,
                        "votes": 1,
                        "mode": "segmentation_disagreement",
                        "raw": [
                            {
                                "variant": "green",
                                "stack_bb": 48.57,
                            },
                            {
                                "variant": "plain",
                                "stack_bb": 48.57,
                            },
                            {
                                "variant": "psm13_t130",
                                "stack_bb": 48.87,
                            },
                        ],
                    },
                    "independent": {
                        "stack_bb": 48.87,
                        "stack_text": "48.87 BB",
                        "confidence": 0.98,
                        "votes": 3,
                        "mode": "independent_segmentation",
                        "raw": [],
                    },
                    "error": None,
                    "elapsed_ms": 584.3,
                },
            )

            fake_image = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            observed_worker_results = []

            original = (
                c.process_stack_change_measurements_async
            )

            def capture_processor(
                changes,
                img,
                coordinator_state,
                **kwargs,
            ):
                ready = dict(
                    kwargs.get(
                        "stack_worker_results"
                    )
                    or {}
                )

                observed_worker_results.append(
                    ready
                )

                return original(
                    changes,
                    img,
                    coordinator_state,
                    **kwargs,
                )

            # Canonical baseline for BB is known and trusted.
            with patch.object(
                c.cv2,
                "imread",
                return_value=fake_image,
            ), patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 48.57,
                },
            ), patch.object(
                c,
                "process_stack_change_measurements_async",
                side_effect=capture_processor,
            ):
                state, progressed, changes = (
                    c.drain_replay_stack_candidates_once(
                        state,
                        final_frame_path="/tmp/0052_full.png",
                        final_frame_ts=FRAME52_TS,
                        replay_records=replay_records,
                    )
                )

            print(
                "progressed:",
                progressed,
            )

            print(
                "processor calls:",
                len(
                    observed_worker_results
                ),
            )

            print(
                "processor ready seats:",
                [
                    sorted(item)
                    for item
                    in observed_worker_results
                ],
            )

            entry = (
                state[
                    "pending_stack_reads"
                ][SEAT]
            )

            print(
                "candidate after drain:",
                entry,
            )

            print(
                "transport after drain:",
                state[
                    "pending_stack_worker_requests"
                ],
            )

            assert observed_worker_results, (
                "REPRODUCED: EOF drain did not call "
                "stack processor"
            )

            assert (
                SEAT
                in observed_worker_results[0]
            ), (
                "REPRODUCED: semantically releasable "
                "completed BB result was not handed "
                "from EOF collector to stack processor"
            )

            # Once the unchanged result reaches the processor,
            # request ownership must be acknowledged/cleared.
            assert (
                entry.get(
                    "stack_worker_request_id"
                )
                is None
            ), (
                "REPRODUCED: BB processor received "
                "completed unchanged result but retained "
                "old request ownership"
            )

            # The ordinary retry machinery must now have
            # selected frame 52, because:
            #
            # 18.891 + 0.45 = 19.341
            # frame 51 = 19.232 (too early)
            # frame 52 = 19.568 (first eligible)
            assert (
                Path(
                    entry[
                        "retry_frame_path"
                    ]
                ).name
                == "0052_full.png"
            ), entry

            assert abs(
                float(
                    entry[
                        "retry_frame_ts"
                    ]
                )
                - FRAME52_TS
            ) < 1e-6

            print(
                "PASS replay EOF ready-result handoff: "
                "completed frame-50 BB result reaches "
                "processor and rearms frame-52 retry"
            )

        finally:
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
