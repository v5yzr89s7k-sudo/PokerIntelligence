from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import time

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


def make_result(
    request_id,
    *,
    frame,
    value,
):
    return {
        "type": "stack_result",
        "request_id": request_id,
        "hand_token": "hand-1",
        "seat": "seat_lower_right",
        "street": "PREFLOP",
        "frame": frame,
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.98,
            "votes": 3,
            "mode": "agreement_verified",
            "raw": [
                {
                    "variant": "plain",
                    "stack_bb": value,
                }
            ],
        },
        "independent": {
            "stack_bb": value,
            "stack_text": f"{value:g} BB",
            "confidence": 0.98,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        },
    }


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_requests = c.STACK_REQUESTS
        old_results = c.STACK_RESULTS

        try:
            c.STACK_REQUESTS = (
                root / "stack_requests.jsonl"
            )
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            state = c.fresh_state()
            state["hand_token"] = "hand-1"
            state["phase"] = "PREFLOP"

            # Reproduce production:
            # physical BTN candidate is already older than the legacy
            # 2.5-second synchronous settlement budget by the time its
            # first asynchronous OCR result is consumed.
            state["pending_stack_reads"] = {
                "seat_lower_right": {
                    "first_change_ts": time.time() - 3.5,
                    "last_change_ts": time.time() - 3.0,
                    "max_mean_diff": 5.0,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "stack_motion",
                        "bet_region_appeared",
                    ],
                    "stack_worker_request_id": "request-1",
                }
            }

            state[
                "pending_stack_worker_requests"
            ] = {}

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            worker_item = {
                "request_id": "request-1",
                "request": {
                    "request_id": "request-1",
                    "seat": "seat_lower_right",
                    "street": "PREFLOP",
                    "frame": "/tmp/0041_full.png",
                    "purpose": "settled",
                },
                "result": make_result(
                    "request-1",
                    frame="/tmp/0041_full.png",
                    value=58.55,
                ),
            }

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    "seat_lower_right": 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    stack_worker_results={
                        "seat_lower_right": worker_item,
                    },
                    frame_path="/tmp/0047_full.png",
                    event_street="PREFLOP",
                )

            # The first unchanged asynchronous result must NOT retire a
            # physically evidenced candidate merely because worker queue /
            # execution time made the candidate older than 2.5 seconds.
            assert (
                "seat_lower_right"
                in state["pending_stack_reads"]
            ), state["pending_stack_reads"]

            entry = state[
                "pending_stack_reads"
            ]["seat_lower_right"]

            # A trusted unchanged asynchronous read is not a failed
            # validation attempt while the physically evidenced candidate
            # may still be developing. It must preserve the finite failure
            # budget for genuinely invalid quantitative reads.
            assert (
                int(
                    entry.get("validation_attempts")
                    or 0
                )
                == 0
            )

            assert (
                entry.get("stack_worker_request_id")
                is None
            )

            # Next cycle must therefore be free to queue a newer frame.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    "seat_lower_right": 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path="/tmp/0047_full.png",
                    event_street="PREFLOP",
                )

            requests = [
                json.loads(line)
                for line in c.STACK_REQUESTS
                .read_text()
                .splitlines()
                if line.strip()
            ]

            assert len(requests) == 1
            assert (
                requests[0]["frame"]
                == "/tmp/0047_full.png"
            )
            assert (
                requests[0]["street"]
                == "PREFLOP"
            )

            print(
                "PASS async stack lifetime: "
                "worker wait does not consume physical "
                "candidate retry eligibility"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
