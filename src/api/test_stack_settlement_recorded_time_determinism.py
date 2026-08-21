from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import time

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_right"  # BTN opponent in July 22; Hero is always "hero".

FRAME_TS = {
    43: 1784748131.702710,
    44: 1784748132.482245,
    45: 1784748132.821169,
    46: 1784748133.151905,
}


def run_case(wall_delays):
    """
    Feed the same recorded-frame semantic timeline while changing only
    real execution delays between coordinator calls.
    """
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
            state["hand_token"] = "july22-test"
            state["phase"] = "PREFLOP"

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            # Frame 43: BTN physical evidence first appears.
            opening = ChangeSet()
            opening.bet_region_appeared = [SEAT]

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: 58.55,
                },
            ):
                c.process_stack_change_measurements_async(
                    opening,
                    img,
                    state,
                    frame_path="/tmp/0043_full.png",
                    frame_ts=FRAME_TS[43],
                    event_street="PREFLOP",
                )

            assert (
                SEAT
                in state["pending_stack_reads"]
            )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            assert abs(
                float(entry["first_change_ts"])
                - FRAME_TS[43]
            ) < 1e-6

            assert abs(
                float(entry["last_change_ts"])
                - FRAME_TS[43]
            ) < 1e-6

            # No request should be queued on the opening frame.
            assert not c.STACK_REQUESTS.exists()

            request_frame = None

            for frame_index, delay in zip(
                (44, 45, 46),
                wall_delays,
            ):
                # Deliberately vary only execution wall time.
                if delay:
                    time.sleep(delay)

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
                        frame_path=(
                            f"/tmp/{frame_index:04d}_full.png"
                        ),
                        frame_ts=FRAME_TS[frame_index],
                        event_street="PREFLOP",
                    )

                if c.STACK_REQUESTS.exists():
                    rows = [
                        json.loads(line)
                        for line in c.STACK_REQUESTS
                        .read_text()
                        .splitlines()
                        if line.strip()
                    ]

                    if rows:
                        request_frame = rows[0]["frame"]
                        break

            assert request_frame is not None

            return request_frame

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


def main():
    fast = run_case(
        wall_delays=(0.0, 0.0, 0.0)
    )

    slow = run_case(
        wall_delays=(0.35, 0.20, 0.10)
    )

    print("fast wall-clock schedule:", fast)
    print("slow wall-clock schedule:", slow)

    assert fast == slow, (
        fast,
        slow,
    )

    # Frame 44 is 779.535 ms after frame 43, already beyond the
    # 450 ms semantic settlement threshold.
    assert fast.endswith(
        "0044_full.png"
    ), fast

    print(
        "PASS BTN recorded-time settlement determinism: "
        "identical replay timestamps queue the same frame "
        "despite different wall-clock execution delays"
    )


if __name__ == "__main__":
    main()
