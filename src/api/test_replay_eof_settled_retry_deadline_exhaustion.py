from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT = "seat_mid_left"


def main():
    old_requests = c.STACK_REQUESTS
    old_results = c.STACK_RESULTS

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        try:
            c.STACK_REQUESTS = (
                root / "stack_requests.jsonl"
            )
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            records = []

            # Three prerecorded frames. The candidate's most
            # recent real quantitative sample is frame 2.
            for index, ts in (
                (1, 99.00),
                (2, 99.80),
                (3, 100.00),
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

                records.append({
                    "index": index,
                    "ts": ts,
                    "frame_path": frame,
                })

            state = c.fresh_state()
            state["phase"] = "FLOP"
            state["hand_token"] = (
                "synthetic-hand"
            )

            # This is NOT the unresolved terminal-sample case.
            #
            # The physical candidate has long since settled,
            # and it has already received a trusted unchanged
            # quantitative sample at t=99.80.
            #
            # Normal retry semantics therefore schedule the
            # next sample at t=100.25. Replay ends at 100.00.
            # There is no prerecorded frame satisfying that
            # next semantic deadline.
            state["pending_stack_reads"] = {
                SEAT: {
                    "hand_token": (
                        "synthetic-hand"
                    ),
                    "first_change_ts": 90.00,
                    "last_change_ts": 90.00,
                    "max_mean_diff": 10.0,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "validation_attempts": 0,
                    "last_stack_sample_ts": 99.80,
                    "retry_not_before_ts": 100.25,
                }
            }

            state[
                "pending_stack_worker_requests"
            ] = {}

            final = records[-1]

            print(
                "ownership before:",
                c.replay_pending_stack_candidates(
                    state
                ),
            )

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 17.85,
                },
            ):
                state, progressed, _ = (
                    c.drain_replay_stack_candidates_once(
                        state,
                        final_frame_path=(
                            final["frame_path"]
                        ),
                        final_frame_ts=(
                            final["ts"]
                        ),
                        replay_records=records,
                    )
                )

            entry = (
                state[
                    "pending_stack_reads"
                ][SEAT]
            )

            outstanding = (
                c.replay_outstanding_transport(
                    state
                )
            )

            candidates = (
                c.replay_pending_stack_candidates(
                    state
                )
            )

            print(
                "progressed:",
                progressed,
            )

            print(
                "candidate after:",
                entry,
            )

            print(
                "outstanding:",
                outstanding,
            )

            print(
                "ownership after:",
                candidates,
            )

            # Critical contract:
            #
            # This settled candidate has already consumed a
            # quantitative retry sample. Its NEXT semantic
            # retry deadline is beyond EOF, and no recorded
            # frame can satisfy it.
            #
            # It must not manufacture an early sample at the
            # final frame merely to keep EOF alive.
            assert (
                not outstanding
                and SEAT not in candidates
            ), (
                "REGRESSION REPRODUCED: settled unchanged "
                "candidate has already sampled prerecorded "
                "evidence, its next semantic retry deadline "
                "lies beyond replay EOF, but EOF still owns "
                "the candidate instead of giving it finite "
                "disposition"
            )

            print(
                "PASS settled unchanged retry deadline "
                "beyond EOF has finite disposition"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
