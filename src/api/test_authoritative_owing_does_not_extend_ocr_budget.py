from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"
STREET = "TURN"
REQUEST_ID = "owing-budget-request-5"


def main():
    state = c.fresh_state()

    state["hand_token"] = "owing-ocr-budget-test"
    state["phase"] = STREET

    state["pending_boundary_route"] = {
        "hand_token": state["hand_token"],
        "previous_street": STREET,
        "next_street": "RIVER",
        "frames": [],
        "required_event_cursor": None,
        "old_street_owing_seats": [SEAT],
    }

    # Four trusted unchanged samples have already completed.
    # This worker result is the fifth and therefore exhausts the
    # ordinary maximum_ocr_attempts=5 unchanged-stack budget.
    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 100.0,
            "last_change_ts": 102.0,
            "max_mean_diff": 5.0,
            "origin_street": STREET,
            "trigger_sources": [
                "stack_motion",
            ],
            "ocr_attempts": 0,
            "validation_attempts": 0,
            "unchanged_stack_reads": 4,
            "last_stack_sample_ts": 102.0,
            "stack_worker_request_id": REQUEST_ID,
            "hand_token": state["hand_token"],
        }
    }

    worker_item = {
        "request_id": REQUEST_ID,
        "request": {
            "request_id": REQUEST_ID,
            "seat": SEAT,
            "street": STREET,
            "frame": "/tmp/0102_full.png",
            "purpose": "settled",
            "hand_token": state["hand_token"],
        },
        "result": {
            "type": "stack_result",
            "request_id": REQUEST_ID,
            "hand_token": state["hand_token"],
            "seat": SEAT,
            "street": STREET,
            "frame": "/tmp/0102_full.png",
            "purpose": "settled",
            "ok": True,
            "reading": {
                "stack_bb": 50.0,
                "stack_text": "50 BB",
                "confidence": 0.98,
                "votes": 3,
                "mode": "test",
                "raw": [],
            },
            "independent": {},
            "error": None,
            "elapsed_ms": 1.0,
        },
    }

    img = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    with patch.object(
        c,
        "_canonical_stack_values",
        return_value={
            SEAT: 50.0,
        },
    ), patch.object(
        c,
        "emit",
    ):
        c.process_stack_change_measurements_async(
            ChangeSet(),
            img,
            state,
            stack_worker_results={
                SEAT: worker_item,
            },
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street=STREET,
            old_street_owing_seats={SEAT},
            frame_path="/tmp/0103_full.png",
            frame_ts=103.0,
            replay_records=[
                {
                    "index": 102,
                    "ts": 102.0,
                    "frame_path": "/tmp/0102_full.png",
                },
                {
                    "index": 103,
                    "ts": 103.0,
                    "frame_path": "/tmp/0103_full.png",
                },
                {
                    "index": 104,
                    "ts": 104.0,
                    "frame_path": "/tmp/0104_full.png",
                },
            ],
        )

    entry = (
        state.get("pending_stack_reads")
        or {}
    ).get(SEAT)

    print()
    print("candidate:", entry)

    assert entry is None, (
        "REGRESSION: motion-only candidate survived "
        "trusted unchanged OCR solely because authoritative "
        "action ownership remained"
    )

    print(
        "motion-only candidate closed after trusted "
        "unchanged OCR despite authoritative owing"
    )

    queued = []

    print(
        "PASS: authoritative owing cannot preserve a "
        "motion-only candidate after trusted unchanged OCR"
    )


if __name__ == "__main__":
    main()
