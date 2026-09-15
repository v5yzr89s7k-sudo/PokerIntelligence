from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cv2
import numpy as np

from src.api import api_event_coordinator as c


SEAT = "seat_upper_right"


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        acquisition_frame = (
            root / "0063_full.png"
        )

        later_frame = (
            root / "0078_full.png"
        )

        # Deliberately distinct pixels so accidental substitution is visible.
        acquisition_img = np.full(
            (696, 934, 3),
            63,
            dtype=np.uint8,
        )

        later_img = np.full(
            (696, 934, 3),
            78,
            dtype=np.uint8,
        )

        assert cv2.imwrite(
            str(acquisition_frame),
            acquisition_img,
        )

        assert cv2.imwrite(
            str(later_frame),
            later_img,
        )

        state = c.fresh_state()

        state["hand_token"] = "startup-acquisition-owner"
        state["phase"] = "PREFLOP"
        state["terminal_action_frozen"] = False
        state["pending_startup_stack_seats"] = [
            SEAT,
        ]
        state["pending_stack_worker_requests"] = {}
        state["startup_stack_last_attempt_ts"] = 0.0

        # Contract under test:
        #
        # the frame that already owns hand acquisition must be installed
        # before startup baseline queuing can observe later live pixels.
        #
        # Current production does not expose/perform that ownership step
        # at acquisition time, so this should initially be RED.
        assert hasattr(
            c,
            "establish_startup_stack_baseline_frame",
        ), (
            "RED: no acquisition-time startup baseline "
            "ownership API exists"
        )

        c.establish_startup_stack_baseline_frame(
            state,
            acquisition_frame,
        )

        assert (
            Path(
                state.get(
                    "startup_stack_baseline_frame"
                )
                or ""
            )
            == acquisition_frame
        ), (
            "RED: acquisition frame did not become "
            "startup baseline owner"
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
            queued.append({
                "seat": seat,
                "street": street,
                "frame": str(frame_path),
                "purpose": purpose,
            })

            return "request-1"

        # Later coordinator pixels are intentionally different.
        # They must have zero authority to redefine startup baseline.
        with patch.object(
            c,
            "queue_stack_worker_request",
            side_effect=fake_queue,
        ):
            c.queue_one_startup_stack_async(
                state,
                frame_path=None,
                local_board_count=0,
                img=later_img,
            )

        assert len(queued) == 1, queued

        request = queued[0]

        print(
            "acquisition_frame:",
            acquisition_frame,
        )

        print(
            "state_baseline_frame:",
            state.get(
                "startup_stack_baseline_frame"
            ),
        )

        print(
            "worker_frame:",
            request["frame"],
        )

        assert (
            Path(request["frame"])
            == acquisition_frame
        ), (
            "RED: later coordinator frame replaced "
            "the acquisition-owned startup baseline"
        )

        print()
        print(
            "PASS: startup baseline ownership is fixed "
            "at Hero acquisition and cannot move later"
        )


if __name__ == "__main__":
    main()
