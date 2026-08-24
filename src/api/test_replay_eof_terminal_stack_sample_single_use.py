from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT = "hero"


def main():
    old_requests = c.STACK_REQUESTS
    old_results = c.STACK_RESULTS

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        try:
            c.STACK_REQUESTS = root / "stack_requests.jsonl"
            c.STACK_RESULTS = root / "stack_results.jsonl"

            records = []

            for index, ts in enumerate(
                (100.00, 100.30, 100.60),
                start=1,
            ):
                frame = root / f"{index:04d}_full.png"

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
            state["hand_token"] = "synthetic-hand"

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

            state["pending_stack_worker_requests"] = {}

            final = records[-1]

            # ----------------------------------------------------
            # EOF cycle 1:
            # terminal sample is legitimately queued.
            # ----------------------------------------------------

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 10.28,
                },
            ):
                _, progressed, _ = (
                    c.drain_replay_stack_candidates_once(
                        state,
                        final_frame_path=final["frame_path"],
                        final_frame_ts=final["ts"],
                        replay_records=records,
                    )
                )

            assert progressed

            entry = state["pending_stack_reads"][SEAT]

            first_request_id = entry.get(
                "stack_worker_request_id"
            )

            assert first_request_id

            first_request = state[
                "pending_stack_worker_requests"
            ][first_request_id]

            assert (
                Path(first_request["frame"]).name
                == final["frame_path"].name
            )

            print(
                "first EOF terminal request:",
                first_request_id,
            )

            # ----------------------------------------------------
            # Simulate the real Gate 3L Hero result.
            #
            # Previous trusted stack = 10.28
            # nearest numeric candidate = 6.9
            # delta = 3.38 > max_drop 3.00
            #
            # Therefore continuity remains unresolved and OCR
            # budget is intentionally not consumed.
            # ----------------------------------------------------

            c.append_jsonl(
                c.STACK_RESULTS,
                {
                    "type": "stack_result",
                    "request_id": first_request_id,
                    "hand_token": "synthetic-hand",
                    "seat": SEAT,
                    "street": "FLOP",
                    "frame": str(final["frame_path"]),
                    "purpose": "settled",
                    "ok": True,
                    "reading": {
                        "stack_bb": 6.9,
                        "stack_text": "6.9 BB",
                        "confidence": 0.50,
                        "votes": 1,
                        "mode": "segmentation_disagreement",
                        "raw": [
                            {
                                "variant": "green",
                                "stack_bb": 6.9,
                            },
                            {
                                "variant": "plain",
                                "stack_bb": 6.9,
                            },
                        ],
                    },
                    "independent": {
                        "stack_bb": 69.0,
                        "stack_text": "69.0 BB",
                        "confidence": 0.98,
                        "votes": 5,
                        "mode": "independent_segmentation",
                        "raw": [],
                    },
                    "error": None,
                    "elapsed_ms": 1.0,
                },
            )

            # ----------------------------------------------------
            # EOF cycle 2:
            # consume that one terminal result.
            # ----------------------------------------------------

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 10.28,
                },
            ):
                c.drain_replay_stack_candidates_once(
                    state,
                    final_frame_path=final["frame_path"],
                    final_frame_ts=final["ts"],
                    replay_records=records,
                )

            entry = state["pending_stack_reads"][SEAT]

            after_result_request_id = entry.get(
                "stack_worker_request_id"
            )

            print(
                "request after terminal result:",
                after_result_request_id,
            )

            print(
                "last numeric evidence:",
                entry.get(
                    "last_numeric_evidence_candidates"
                ),
            )

            # ----------------------------------------------------
            # EOF cycle 3:
            #
            # This is the regression boundary.
            #
            # The finite EOF terminal sample has already been
            # consumed. Another drain cycle must NOT manufacture
            # another request against the same final frame.
            # ----------------------------------------------------

            before_request_ids = set(
                (
                    state.get(
                        "pending_stack_worker_requests"
                    )
                    or {}
                ).keys()
            )

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 10.28,
                },
            ):
                c.drain_replay_stack_candidates_once(
                    state,
                    final_frame_path=final["frame_path"],
                    final_frame_ts=final["ts"],
                    replay_records=records,
                )

            after_request_ids = set(
                (
                    state.get(
                        "pending_stack_worker_requests"
                    )
                    or {}
                ).keys()
            )

            new_request_ids = (
                after_request_ids
                - before_request_ids
            )

            print(
                "requests before third EOF cycle:",
                sorted(before_request_ids),
            )

            print(
                "requests after third EOF cycle:",
                sorted(after_request_ids),
            )

            print(
                "new requests:",
                sorted(new_request_ids),
            )

            assert not new_request_ids, (
                "REGRESSION REPRODUCED: completed "
                "numeric-but-continuity-unresolved EOF "
                "terminal stack sample is level-triggered; "
                "the next EOF drain cycle queues another "
                "request against the same final recorded "
                "frame, so replay can never drain"
            )

            print(
                "PASS replay EOF terminal stack sample "
                "is single-use"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
