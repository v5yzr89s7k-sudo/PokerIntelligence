from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_right"  # July 22 BTN opponent. Hero is always "hero".

OPEN_TS = 1784748131.702710
FIRST_REQUEST_TS = 1784748132.482245  # frame 44

FRAME_TS = {
    44: 1784748132.482245,
    46: 1784748133.151905,
    49: 1784748134.184605,
}


def unchanged_result(request_id):
    value = 58.55

    return {
        "request_id": request_id,
        "request": {
            "request_id": request_id,
            "hand_token": "hand-1",
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0044_full.png",
            "purpose": "settled",
        },
        "result": {
            "type": "stack_result",
            "request_id": request_id,
            "hand_token": "hand-1",
            "seat": SEAT,
            "street": "PREFLOP",
            "frame": "/tmp/0044_full.png",
            "purpose": "settled",
            "ok": True,
            "reading": {
                "stack_bb": value,
                "stack_text": "58.55 BB",
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
                "stack_text": "58.55 BB",
                "confidence": 0.98,
                "votes": 5,
                "mode": "independent_segmentation",
                "raw": [],
            },
        },
    }


def consume_at(frame_index):
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
                    "stack_worker_request_id": "request-1",
                    # Semantic timestamp of the deterministic first sample.
                    "last_stack_sample_ts": FIRST_REQUEST_TS,
                }
            }

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

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
                    stack_worker_results={
                        SEAT: unchanged_result(
                            "request-1"
                        ),
                    },
                    frame_path=(
                        f"/tmp/{frame_index:04d}_full.png"
                    ),
                    frame_ts=FRAME_TS[frame_index],
                    event_street="PREFLOP",
                )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            return {
                "retry_not_before_ts": entry.get(
                    "retry_not_before_ts"
                ),
                "stack_worker_request_id": entry.get(
                    "stack_worker_request_id"
                ),
                "requests_exist": (
                    c.STACK_REQUESTS.exists()
                    and bool(
                        c.STACK_REQUESTS
                        .read_text()
                        .strip()
                    )
                ),
            }

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


def main():
    early = consume_at(46)
    late = consume_at(49)

    print("early completion:", early)
    print("late completion :", late)

    expected = (
        FIRST_REQUEST_TS + 0.45
    )

    assert early[
        "retry_not_before_ts"
    ] is not None, (
        "production has no semantic retry deadline yet"
    )

    assert late[
        "retry_not_before_ts"
    ] is not None, (
        "production has no semantic retry deadline yet"
    )

    assert abs(
        float(
            early["retry_not_before_ts"]
        ) - expected
    ) < 1e-6

    assert abs(
        float(
            late["retry_not_before_ts"]
        ) - expected
    ) < 1e-6

    assert (
        early["retry_not_before_ts"]
        == late["retry_not_before_ts"]
    )

    # Consuming the result must not immediately publish another request.
    # The future recorded timeline owns retry release.
    assert not early["requests_exist"]
    assert not late["requests_exist"]

    assert (
        early["stack_worker_request_id"]
        is None
    )
    assert (
        late["stack_worker_request_id"]
        is None
    )

    print(
        "PASS semantic stack retry deadline: "
        "worker completion time cannot choose retry timing"
    )


if __name__ == "__main__":
    main()
