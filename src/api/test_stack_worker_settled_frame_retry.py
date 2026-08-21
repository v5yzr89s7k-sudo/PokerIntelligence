from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_right"  # July 22 BTN opponent; Hero is always "hero".

OPEN_TS = 1784748131.702710
FIRST_REQUEST_TS = 1784748132.482245
RETRY_DEADLINE = FIRST_REQUEST_TS + 0.45

BEFORE_DEADLINE_TS = 1784748132.821169  # frame 45
AFTER_DEADLINE_TS = 1784748133.151905   # frame 46


def result_for(
    request_id,
    *,
    hand_token,
    seat,
    street,
    frame,
    value,
):
    return {
        "type": "stack_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "seat": seat,
        "street": street,
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


def read_requests():
    if not c.STACK_REQUESTS.exists():
        return []

    return [
        json.loads(line)
        for line in c.STACK_REQUESTS.read_text().splitlines()
        if line.strip()
    ]


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

            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": OPEN_TS,
                    "last_change_ts": OPEN_TS,
                    "max_mean_diff": 5.0,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "bet_region_appeared",
                    ],
                }
            }

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            first_frame = "/tmp/0044_full.png"

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path=first_frame,
                    frame_ts=FIRST_REQUEST_TS,
                    event_street="PREFLOP",
                )

            requests = read_requests()

            assert len(requests) == 1, requests

            first = requests[0]

            assert first["frame"] == first_frame

            first_id = first["request_id"]

            assert abs(
                float(
                    state["pending_stack_reads"][SEAT][
                        "last_stack_sample_ts"
                    ]
                ) - FIRST_REQUEST_TS
            ) < 1e-6

            c.append_jsonl(
                c.STACK_RESULTS,
                result_for(
                    first_id,
                    hand_token="hand-1",
                    seat=SEAT,
                    street="PREFLOP",
                    frame=first_frame,
                    value=58.55,
                ),
            )

            ready = (
                c.collect_ready_stack_worker_results(
                    state
                )
            )

            # Consume the trusted unchanged result.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    stack_worker_results=ready,
                    frame_path="/tmp/0045_full.png",
                    frame_ts=BEFORE_DEADLINE_TS,
                    event_street="PREFLOP",
                )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            assert abs(
                float(
                    entry["retry_not_before_ts"]
                ) - RETRY_DEADLINE
            ) < 1e-6

            assert (
                entry.get("stack_worker_request_id")
                is None
            )

            # Still before the semantic deadline: no retry.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path="/tmp/0045_full.png",
                    frame_ts=BEFORE_DEADLINE_TS,
                    event_street="PREFLOP",
                )

            requests = read_requests()

            assert len(requests) == 1, requests

            # First recorded frame at/after the deadline may publish.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path="/tmp/0046_full.png",
                    frame_ts=AFTER_DEADLINE_TS,
                    event_street="PREFLOP",
                )

            requests = read_requests()

            assert len(requests) == 2, requests

            second = requests[1]

            assert second["frame"] == "/tmp/0046_full.png"
            assert second["street"] == "PREFLOP"
            assert (
                second["request_id"]
                != first["request_id"]
            )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            assert abs(
                float(
                    entry["last_stack_sample_ts"]
                ) - AFTER_DEADLINE_TS
            ) < 1e-6

            assert (
                entry.get("retry_not_before_ts")
                is None
            )

            print(
                "PASS settled-frame retry: unchanged OCR "
                "preserves candidate, blocks before semantic "
                "deadline, then queues exactly once at the "
                "first eligible recorded frame"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
