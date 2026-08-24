from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_mid_right"
BASELINE = 136.01


def unchanged_worker_item(request_id, frame):
    return {
        "request_id": request_id,
        "request": {
            "request_id": request_id,
            "hand_token": "hand-1",
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": frame,
            "purpose": "settled",
        },
        "result": {
            "type": "stack_result",
            "request_id": request_id,
            "hand_token": "hand-1",
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": frame,
            "purpose": "settled",
            "ok": True,
            "reading": {
                "stack_bb": BASELINE,
                "stack_text": "136.01 BB",
                "confidence": 0.98,
                "votes": 2,
                "mode": "agreement_verified",
                "raw": [
                    {
                        "variant": "plain",
                        "stack_bb": BASELINE,
                    },
                    {
                        "variant": "green",
                        "stack_bb": BASELINE,
                    },
                ],
            },
            "independent": {
                "stack_bb": BASELINE,
                "stack_text": "136.01 BB",
                "confidence": 0.98,
                "votes": 5,
                "mode": "independent_segmentation",
                "raw": [],
            },
        },
    }


def consume_unchanged(state, number):
    request_id = f"request-{number}"
    frame = f"/tmp/{40 + number:04d}_full.png"

    entry = state[
        "pending_stack_reads"
    ][SEAT]

    entry["stack_worker_request_id"] = request_id
    entry["last_stack_sample_ts"] = float(number)

    with patch.object(
        c,
        "_canonical_stack_values",
        return_value={
            SEAT: BASELINE,
        },
    ):
        c.process_stack_change_measurements_async(
            ChangeSet(),
            np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            ),
            state,
            stack_worker_results={
                SEAT: unchanged_worker_item(
                    request_id,
                    frame,
                ),
            },
            frame_path=frame,
            frame_ts=float(number),
            event_street="PREFLOP",
        )


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "PREFLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "hand_token": "hand-1",
            "first_change_ts": 0.0,
            "last_change_ts": 0.0,
            "max_mean_diff": 20.0,
            "origin_street": "PREFLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "validation_attempts": 0,
        }
    }

    state[
        "pending_stack_worker_requests"
    ] = {}

    # The first unchanged asynchronous result must remain legal.
    # This preserves the established worker-latency contract.
    consume_unchanged(
        state,
        1,
    )

    assert (
        SEAT
        in state["pending_stack_reads"]
    ), (
        "first trusted unchanged read must not retire "
        "a physical candidate"
    )

    first = state[
        "pending_stack_reads"
    ][SEAT]

    assert int(
        first.get(
            "validation_attempts"
        )
        or 0
    ) == 0, (
        "trusted unchanged evidence must not consume "
        "the ordinary invalid-OCR budget"
    )

    print(
        "after first unchanged:",
        first,
    )

    # Production already defines maximum_ocr_attempts = 5.
    # Consecutive trusted unchanged physical reads need their
    # own finite lifecycle using that established safety bound.
    for number in range(2, 6):
        if (
            SEAT
            not in state[
                "pending_stack_reads"
            ]
        ):
            break

        consume_unchanged(
            state,
            number,
        )

        print(
            f"after unchanged {number}:",
            (
                state[
                    "pending_stack_reads"
                ].get(SEAT)
            ),
        )

    assert (
        SEAT
        not in state["pending_stack_reads"]
    ), (
        "REGRESSION REPRODUCED: five consecutive trusted "
        "unchanged quantitative reads leave a physical "
        "candidate alive indefinitely; the existing hard "
        "retry safety bound never applies, allowing dozens "
        "of identical OCR reads through the remaining replay"
    )

    print(
        "PASS trusted unchanged physical candidate "
        "retires after bounded consecutive evidence"
    )


if __name__ == "__main__":
    main()
