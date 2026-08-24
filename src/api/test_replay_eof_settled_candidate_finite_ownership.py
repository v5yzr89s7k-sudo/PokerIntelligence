from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT = "seat_mid_right"


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

            # Candidate is already semantically settled by EOF.
            # This matches the non-Hero Gate 3R survivors:
            # their last_change_ts is well before the final
            # recorded timestamp.
            state["pending_stack_reads"] = {
                SEAT: {
                    "hand_token": (
                        "synthetic-hand"
                    ),
                    "first_change_ts": 99.00,
                    "last_change_ts": 99.00,
                    "last_stack_sample_ts": 100.60,
                    "origin_street": "FLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "validation_attempts": 0,
                    "retry_not_before_ts": (
                        101.05
                    ),
                }
            }

            state[
                "pending_stack_worker_requests"
            ] = {}

            final = records[-1]

            print(
                "candidate before EOF drain:",
                state[
                    "pending_stack_reads"
                ][SEAT],
            )

            print(
                "ownership before EOF drain:",
                c.replay_pending_stack_candidates(
                    state
                ),
            )

            # At EOF recorded time cannot advance to the
            # retry deadline. The drain must nevertheless
            # give this hand-owned settled candidate a finite
            # disposition rather than leave it permanently
            # blocking completion.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 136.01,
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

            print(
                "progressed:",
                progressed,
            )

            candidate = (
                state.get(
                    "pending_stack_reads"
                )
                or {}
            ).get(SEAT)

            print(
                "candidate after EOF drain:",
                candidate,
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
                "outstanding transport:",
                outstanding,
            )

            print(
                "EOF drain candidates:",
                candidates,
            )

            # We do NOT require the candidate to be deleted.
            # It may remain represented as unresolved semantic
            # evidence. The contract is only that EOF ownership
            # must be finite.
            assert (
                outstanding
                or SEAT not in candidates
            ), (
                "REGRESSION REPRODUCED: a settled "
                "hand-owned stack candidate reaches EOF "
                "with no outstanding transport, but "
                "replay_pending_stack_candidates still "
                "claims it owns drainable prerecorded "
                "work; recorded time cannot advance, so "
                "the coordinator prints REPLAY_DRAIN "
                "forever"
            )

            print(
                "PASS settled EOF candidate has "
                "finite replay ownership"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
