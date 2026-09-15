from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT_A = "seat_upper_right"
SEAT_B = "seat_lower_right"


def main():
    print()
    print("=" * 78)
    print("ASYNC STARTUP STACK — IMMUTABLE HAND-START FRAME")
    print("=" * 78)

    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        hand_start_frame = (
            root / "hand_start.png"
        )

        later_frame = (
            root / "later_live_frame.png"
        )

        # Distinct pixels make accidental frame substitution observable.
        hand_start_img = np.full(
            (696, 934, 3),
            25,
            dtype=np.uint8,
        )

        later_img = np.full(
            (696, 934, 3),
            225,
            dtype=np.uint8,
        )

        assert cv2.imwrite(
            str(hand_start_frame),
            hand_start_img,
        )

        assert cv2.imwrite(
            str(later_frame),
            later_img,
        )

        state = c.fresh_state()

        state["hand_token"] = (
            "immutable-startup-frame-test"
        )

        state["phase"] = "PREFLOP"

        state["terminal_action_frozen"] = False

        state["pending_startup_stack_seats"] = [
            SEAT_A,
            SEAT_B,
        ]

        state["pending_stack_worker_requests"] = {}

        state["startup_stack_last_attempt_ts"] = 0.0

        # This is the authoritative immutable frame captured for
        # hand bootstrap. All startup baseline work for this hand
        # must use this same frame even if queued later.
        state["startup_stack_baseline_frame"] = str(
            hand_start_frame
        )

        queued = []

        def fake_queue(
            state_arg,
            *,
            seat,
            street,
            frame_path,
            purpose,
        ):
            request_id = (
                f"request-{len(queued) + 1}"
            )

            queued.append({
                "request_id": request_id,
                "seat": seat,
                "street": street,
                "frame": frame_path,
                "purpose": purpose,
            })

            state_arg.setdefault(
                "pending_stack_worker_requests",
                {},
            )[request_id] = {
                "request_id": request_id,
                "seat": seat,
                "street": street,
                "frame": frame_path,
                "purpose": purpose,
                "hand_token": state_arg.get(
                    "hand_token"
                ),
            }

            return request_id

        # First queue cycle occurs while current pixels happen to
        # equal the hand-start image.
        with patch.object(
            c,
            "queue_stack_worker_request",
            side_effect=fake_queue,
        ), patch.object(
            c,
            "materialize_worker_frame",
            return_value=str(later_frame),
        ):
            c.queue_one_startup_stack_async(
                state,
                frame_path=None,
                local_board_count=0,
                img=hand_start_img,
            )

        assert queued, (
            "first startup baseline request "
            "was not queued"
        )

        first = queued[-1]

        print()
        print("first request:", first)

        # Simulate completion so the next unresolved seat can queue.
        first_id = first["request_id"]

        state.get(
            "pending_stack_worker_requests",
            {},
        ).pop(
            first_id,
            None,
        )

        state["pending_startup_stack_seats"] = [
            SEAT_B,
        ]

        state["startup_stack_last_attempt_ts"] = 0.0

        # Time has advanced and the current live image is now very
        # different. The second startup baseline must STILL use the
        # original immutable hand-start frame.
        with patch.object(
            c,
            "queue_stack_worker_request",
            side_effect=fake_queue,
        ), patch.object(
            c,
            "materialize_worker_frame",
            return_value=str(later_frame),
        ):
            c.queue_one_startup_stack_async(
                state,
                frame_path=None,
                local_board_count=0,
                img=later_img,
            )

        assert len(queued) == 2, queued

        second = queued[-1]

        print("second request:", second)

        expected = str(hand_start_frame)

        print()
        print(
            "authoritative hand-start frame:",
            expected,
        )

        print(
            "first worker frame:",
            first["frame"],
        )

        print(
            "second worker frame:",
            second["frame"],
        )

        assert first["frame"] == expected, (
            "BUG: first startup baseline request "
            "did not use immutable hand-start frame"
        )

        assert second["frame"] == expected, (
            "BUG: later startup baseline request "
            "used current live pixels instead of "
            "immutable hand-start frame"
        )

        assert (
            first["frame"]
            == second["frame"]
        ), (
            "BUG: startup baseline frame ownership "
            "changes between seats in the same hand"
        )

        print()
        print(
            "PASS: all startup baseline requests "
            "own the same immutable hand-start frame"
        )


if __name__ == "__main__":
    main()
