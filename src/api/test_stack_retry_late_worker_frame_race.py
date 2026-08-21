from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_right"  # July 22 BTN opponent. Hero is always "hero".

OPEN_TS = 1784748131.702710

FRAME_TS = {
    44: 1784748132.482245,
    45: 1784748132.821169,
    46: 1784748133.151905,
    47: 1784748133.509549,
    48: 1784748133.843657,
    49: 1784748134.184605,
}

REPLAY_RECORDS = [
    {
        "index": frame,
        "ts": ts,
        "frame_path": Path(
            f"/tmp/{frame:04d}_full.png"
        ),
    }
    for frame, ts in FRAME_TS.items()
]

FIRST_FRAME = "/tmp/0044_full.png"
FIRST_TS = FRAME_TS[44]
RETRY_DEADLINE = FIRST_TS + 0.45


def worker_item(request_id):
    value = 58.55

    request = {
        "request_id": request_id,
        "hand_token": "hand-1",
        "seat": SEAT,
        "street": "PREFLOP",
        "frame": FIRST_FRAME,
        "purpose": "settled",
    }

    result = {
        "type": "stack_result",
        **request,
        "ok": True,
        "reading": {
            "stack_bb": value,
            "stack_text": "58.55 BB",
            "confidence": 0.98,
            "votes": 3,
            "mode": "agreement_verified",
            "raw": [],
        },
        "independent": {
            "stack_bb": value,
            "stack_text": "58.55 BB",
            "confidence": 0.98,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        },
    }

    return {
        "request_id": request_id,
        "request": request,
        "result": result,
    }


def requests():
    if not c.STACK_REQUESTS.exists():
        return []

    return [
        json.loads(line)
        for line in c.STACK_REQUESTS.read_text().splitlines()
        if line.strip()
    ]


def run_case(result_frame):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_requests = c.STACK_REQUESTS
        old_results = c.STACK_RESULTS

        try:
            c.STACK_REQUESTS = root / "stack_requests.jsonl"
            c.STACK_RESULTS = root / "stack_results.jsonl"

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

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={SEAT: 58.55},
            ):
                # Deterministic first sample = frame 44.
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path=FIRST_FRAME,
                    frame_ts=FIRST_TS,
                    event_street="PREFLOP",
                    replay_records=REPLAY_RECORDS,
                )

            rows = requests()
            assert len(rows) == 1, rows

            first_id = rows[0]["request_id"]

            # While the worker is still outstanding, advance semantic
            # replay frames. No duplicate request is legal.
            for frame in range(45, result_frame):
                with patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={SEAT: 58.55},
                ):
                    c.process_stack_change_measurements_async(
                        ChangeSet(),
                        img,
                        state,
                        frame_path=f"/tmp/{frame:04d}_full.png",
                        frame_ts=FRAME_TS[frame],
                        event_street="PREFLOP",
                    )

                assert len(requests()) == 1

            # Worker finally returns unchanged on this semantic frame.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={SEAT: 58.55},
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    stack_worker_results={
                        SEAT: worker_item(first_id)
                    },
                    frame_path=f"/tmp/{result_frame:04d}_full.png",
                    frame_ts=FRAME_TS[result_frame],
                    event_street="PREFLOP",
                    replay_records=REPLAY_RECORDS,
                )

            entry = state["pending_stack_reads"][SEAT]

            assert abs(
                float(entry["retry_not_before_ts"])
                - RETRY_DEADLINE
            ) < 1e-6

            # Next coordinator cycle uses the same current semantic frame.
            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={SEAT: 58.55},
            ):
                c.process_stack_change_measurements_async(
                    ChangeSet(),
                    img,
                    state,
                    frame_path=f"/tmp/{result_frame:04d}_full.png",
                    frame_ts=FRAME_TS[result_frame],
                    event_street="PREFLOP",
                    replay_records=REPLAY_RECORDS,
                )

            rows = requests()

            assert len(rows) == 2, rows

            return Path(rows[1]["frame"]).name

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


def main():
    early = run_case(46)
    late = run_case(49)

    print("early worker completion retry:", early)
    print("late worker completion retry :", late)

    # Desired deterministic replay invariant:
    # worker completion latency must not select a different OCR image.
    assert early == late, (
        "REPRODUCED: asynchronous worker completion still "
        f"changes retry frame: early={early} late={late}"
    )

    print(
        "PASS: retry frame is independent of worker completion"
    )


if __name__ == "__main__":
    main()
