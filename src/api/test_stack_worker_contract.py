from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from unittest.mock import patch

from src.api import api_stack_worker as worker


def make_frame(path):
    img = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    assert cv2.imwrite(
        str(path),
        img,
    )


def main():
    with TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.png"
        make_frame(frame)

        ordinary = {
            "stack_bb": 53.41,
            "stack_text": "53.41 BB",
            "confidence": 0.50,
            "votes": 1,
            "mode": "segmentation_disagreement",
            "raw": [],
        }

        independent = {
            "stack_bb": 53.41,
            "stack_text": "53.41 BB",
            "confidence": 0.98,
            "votes": 5,
            "mode": "independent_segmentation",
            "raw": [],
        }

        with (
            patch.object(
                worker,
                "read_stack",
                return_value=ordinary,
            ),
            patch.object(
                worker,
                "read_stack_independent_consensus",
                return_value=independent,
            ),
        ):
            result = worker.process_request({
                "type": "stack_request",
                "request_id": "settled-1",
                "hand_token": "hand-1",
                "seat": "hero",
                "street": "PREFLOP",
                "frame": str(frame),
                "purpose": "settled",
            })

        assert result["ok"] is True
        assert result["reading"] == ordinary
        assert result["independent"] == independent
        assert result["seat"] == "hero"
        assert result["street"] == "PREFLOP"
        assert result["purpose"] == "settled"
        assert result["elapsed_ms"] >= 0.0

        # Baseline mode deliberately avoids the correlated reader.
        with (
            patch.object(
                worker,
                "read_stack",
            ) as ordinary_mock,
            patch.object(
                worker,
                "read_stack_independent_consensus",
                return_value=independent,
            ),
        ):
            baseline = worker.process_request({
                "type": "stack_request",
                "request_id": "baseline-1",
                "hand_token": "hand-1",
                "seat": "hero",
                "street": "PREFLOP",
                "frame": str(frame),
                "purpose": "baseline",
            })

        assert baseline["ok"] is True
        assert baseline["reading"] is None
        assert baseline["independent"] == independent
        ordinary_mock.assert_not_called()

        print(
            "PASS stack worker contract: "
            "OCR is perception-only and returns serializable "
            "ordinary/independent evidence without poker semantics"
        )


if __name__ == "__main__":
    main()
