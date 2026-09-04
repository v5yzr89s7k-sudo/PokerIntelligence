from pathlib import Path
import json
import tempfile

import cv2
import numpy as np

import src.api.api_event_coordinator as c


def main():
    original_requests = c.BOARD_REQUESTS
    original_capture_dir = c.CAPTURE_DIR

    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            c.BOARD_REQUESTS = (
                root / "board_requests.jsonl"
            )
            c.CAPTURE_DIR = (
                root / "captures"
            )

            # --------------------------------------------------
            # Contract 1
            #
            # No path + no image must never publish Board work.
            # --------------------------------------------------
            state = c.fresh_state()
            state["phase"] = "PREFLOP"
            state["hand_token"] = "test-hand"

            state = c.queue_board_request(
                state,
                3,
                None,
                img=None,
            )

            assert (
                not c.BOARD_REQUESTS.exists()
            ), (
                "Board published a request "
                "without an owned frame"
            )

            assert (
                state.get("board_request_id")
                is None
            ), (
                "Board retained request ownership "
                "despite no frame"
            )

            print(
                "PASS: null Board frame is deferred"
            )

            # --------------------------------------------------
            # Contract 2
            #
            # Live SCK image must be materialized before
            # worker-request publication.
            # --------------------------------------------------
            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            state = c.queue_board_request(
                state,
                3,
                None,
                img=img,
            )

            assert c.BOARD_REQUESTS.exists()

            lines = (
                c.BOARD_REQUESTS
                .read_text()
                .splitlines()
            )

            assert len(lines) == 1, lines

            row = json.loads(
                lines[0]
            )

            frame = row.get("frame")

            assert frame not in (
                None,
                "",
                "None",
            ), (
                f"invalid Board frame "
                f"published: {frame!r}"
            )

            frame_path = Path(frame)

            assert frame_path.exists(), (
                f"materialized Board frame "
                f"missing: {frame_path}"
            )

            assert (
                "acr_table_sck_board_"
                in frame_path.name
            ), frame_path.name

            loaded = cv2.imread(
                str(frame_path)
            )

            assert loaded is not None

            assert loaded.shape[:2] == (
                696,
                934,
            )

            assert (
                row.get("request_id")
                == state.get(
                    "board_request_id"
                )
            )

            assert (
                row.get("expected_len")
                == 3
            )

            print(
                "PASS: SCK Board frame materialized"
            )
            print(
                "request:",
                row["request_id"][:8],
            )
            print(
                "frame:",
                frame_path,
            )
            print(
                "frame exists:",
                frame_path.exists(),
            )
            print(
                "frame readable:",
                loaded is not None,
            )

            # --------------------------------------------------
            # Contract 3
            #
            # Legacy/replay path already owns a filesystem
            # frame and must not rematerialize it.
            # --------------------------------------------------
            legacy = root / "legacy_frame.png"

            assert cv2.imwrite(
                str(legacy),
                img,
            )

            state2 = c.fresh_state()
            state2["phase"] = "PREFLOP"
            state2["hand_token"] = "legacy-hand"

            c.BOARD_REQUESTS.unlink()

            state2 = c.queue_board_request(
                state2,
                3,
                legacy,
                img=None,
            )

            rows = [
                json.loads(line)
                for line
                in c.BOARD_REQUESTS
                .read_text()
                .splitlines()
            ]

            assert len(rows) == 1

            assert (
                rows[0]["frame"]
                == str(legacy)
            ), rows[0]

            print(
                "PASS: legacy/replay Board path preserved"
            )

            print()
            print(
                "PASS board worker frame ownership"
            )

    finally:
        c.BOARD_REQUESTS = original_requests
        c.CAPTURE_DIR = original_capture_dir


if __name__ == "__main__":
    main()
