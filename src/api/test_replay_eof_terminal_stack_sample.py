from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT = "hero"


def main():
    old_requests = c.STACK_REQUESTS

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        try:
            c.STACK_REQUESTS = (
                root / "stack_requests.jsonl"
            )

            # Synthetic prerecorded frames. Their numeric timestamps
            # intentionally do not correspond to any real poker hand.
            records = []

            for index, ts in enumerate(
                (100.00, 100.30, 100.60),
                start=1,
            ):
                frame = (
                    root
                    / f"{index:04d}_full.png"
                )

                cv2.imwrite(
                    str(frame),
                    np.zeros(
                        (696, 934, 3),
                        dtype=np.uint8,
                    ),
                )

                records.append(
                    {
                        "index": index,
                        "ts": ts,
                        "frame_path": frame,
                    }
                )

            state = c.fresh_state()
            state["phase"] = "FLOP"
            state["hand_token"] = "synthetic-hand"

            # Candidate changed too near EOF to satisfy the ordinary
            # quiet-time gate. It has already consumed an unchanged
            # quantitative sample and owns no worker now.
            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": 100.10,
                    "last_change_ts": 100.40,
                    "last_stack_sample_ts": 100.30,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "retry_not_before_ts": 100.75,
                    "validation_attempts": 0,
                }
            }

            state[
                "pending_stack_worker_requests"
            ] = {}

            final = records[-1]

            _, progressed, _ = (
                c.drain_replay_stack_candidates_once(
                    state,
                    final_frame_path=(
                        final["frame_path"]
                    ),
                    final_frame_ts=final["ts"],
                    replay_records=records,
                )
            )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            request_id = entry.get(
                "stack_worker_request_id"
            )

            print(
                "progressed:",
                progressed,
            )

            print(
                "request id:",
                request_id,
            )

            print(
                "last sample:",
                entry.get(
                    "last_stack_sample_ts"
                ),
            )

            print(
                "retry deadline:",
                entry.get(
                    "retry_not_before_ts"
                ),
            )

            assert request_id, (
                "REPRODUCED: replay EOF candidate "
                "cannot queue a finite terminal "
                "stack sample when recorded time "
                "ends before ordinary settlement"
            )

            request = state[
                "pending_stack_worker_requests"
            ][request_id]

            assert (
                Path(request["frame"]).name
                == final["frame_path"].name
            ), (
                "EOF terminal sample must use the "
                "newest recorded frame"
            )

            assert abs(
                float(
                    entry[
                        "last_stack_sample_ts"
                    ]
                )
                - float(final["ts"])
            ) < 1e-9

            assert progressed

            print(
                "PASS replay EOF terminal stack "
                "sample contract"
            )

        finally:
            c.STACK_REQUESTS = old_requests


if __name__ == "__main__":
    main()
