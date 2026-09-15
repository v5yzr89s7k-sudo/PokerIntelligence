from pathlib import Path
import tempfile

import cv2
import numpy as np

from src.api import api_event_coordinator as c


def base_state():
    return {
        "hand_token": "hand-test",
        "phase": "PREFLOP",
        "terminal_action_frozen": False,
        "pending_startup_stack_seats": [
            "seat_upper_right",
        ],
        "pending_stack_worker_requests": {},
        "startup_stack_last_attempt_ts": 0.0,
    }


def main():
    original_requests = c.STACK_REQUESTS
    original_capture_dir = c.CAPTURE_DIR

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        try:
            c.STACK_REQUESTS = root / "stack_requests.jsonl"
            c.CAPTURE_DIR = root / "captures"
            c.CAPTURE_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            # --------------------------------------------------
            # No filesystem frame and no image:
            # must defer rather than queue an empty path.
            # --------------------------------------------------
            state = base_state()

            state = c.queue_one_startup_stack_async(
                state,
                None,
                local_board_count=0,
                img=None,
            )

            assert not c.STACK_REQUESTS.exists() or not (
                c.STACK_REQUESTS.read_text().strip()
            )

            assert not state.get(
                "pending_stack_worker_requests"
            )

            print(
                "PASS: null live baseline frame is deferred"
            )

            # --------------------------------------------------
            # Live SCK in-memory image:
            # must become a real immutable frame.
            # --------------------------------------------------
            state = base_state()

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            state = c.queue_one_startup_stack_async(
                state,
                None,
                local_board_count=0,
                img=img,
            )

            transport = (
                state.get(
                    "pending_stack_worker_requests"
                )
                or {}
            )

            assert len(transport) == 1

            request_id, request = next(
                iter(transport.items())
            )

            assert request.get("purpose") == "baseline"
            assert request.get("seat") == "seat_upper_right"

            frame = Path(request.get("frame") or "")

            assert frame.exists(), (
                f"materialized baseline frame missing: {frame}"
            )

            assert frame.is_file()

            decoded = cv2.imread(str(frame))

            assert decoded is not None, (
                f"materialized frame unreadable: {frame}"
            )

            assert "acr_table_sck_startup_stack_" in frame.name, (
                f"unexpected materialization name: {frame.name}"
            )

            print(
                "PASS: live SCK startup baseline owns "
                "a real immutable frame"
            )
            print("request:", request_id[:8])
            print("frame:", frame)

            # --------------------------------------------------
            # Replay/legacy durable filesystem frame:
            # preserve it unchanged.
            # --------------------------------------------------
            durable = root / "replay_frame.png"

            assert cv2.imwrite(
                str(durable),
                img,
            )

            state = base_state()
            state["startup_stack_last_attempt_ts"] = 0.0

            state = c.queue_one_startup_stack_async(
                state,
                durable,
                local_board_count=0,
                img=None,
            )

            transport = (
                state.get(
                    "pending_stack_worker_requests"
                )
                or {}
            )

            assert len(transport) == 1

            _, request = next(
                iter(transport.items())
            )

            assert Path(request["frame"]) == durable

            print(
                "PASS: replay/legacy baseline path preserved"
            )

        finally:
            c.STACK_REQUESTS = original_requests
            c.CAPTURE_DIR = original_capture_dir

    print()
    print(
        "PASS async startup-stack frame ownership"
    )


if __name__ == "__main__":
    main()
