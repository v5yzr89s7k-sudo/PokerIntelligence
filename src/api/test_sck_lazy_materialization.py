from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as coordinator


def main():
    fake = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    # --------------------------------------------------------
    # Acquisition contract:
    # SCK capture itself must not write a compatibility PNG.
    # --------------------------------------------------------

    class FakeSource:
        def read(self):
            return fake.copy()

    previous = coordinator._SCK_FRAME_SOURCE

    try:
        coordinator._SCK_FRAME_SOURCE = FakeSource()

        with patch.object(
            coordinator.cv2,
            "imwrite",
            side_effect=AssertionError(
                "SCK acquisition performed disk write"
            ),
        ):
            img, path = coordinator.capture_sck_live()

        assert img.shape == (696, 934, 3)
        assert path is None

    finally:
        coordinator._SCK_FRAME_SOURCE = previous

    # --------------------------------------------------------
    # Worker ownership contract:
    # explicit materialization writes exactly once and returns
    # an immutable unique path.
    # --------------------------------------------------------

    writes = []

    def fake_imwrite(path, image):
        writes.append(
            (
                path,
                image.shape,
            )
        )
        return True

    with patch.object(
        coordinator.cv2,
        "imwrite",
        side_effect=fake_imwrite,
    ):
        first = coordinator.materialize_worker_frame(
            fake,
            purpose="hero",
            request_id="request-a",
        )

        second = coordinator.materialize_worker_frame(
            fake,
            purpose="board",
            request_id="request-b",
        )

    assert len(writes) == 2
    assert first != second

    assert first.name == (
        "acr_table_sck_hero_request-a.png"
    )

    assert second.name == (
        "acr_table_sck_board_request-b.png"
    )

    assert writes[0][1] == (696, 934, 3)
    assert writes[1][1] == (696, 934, 3)

    print(
        "PASS SCK lazy materialization: "
        "ordinary acquisition is memory-only; "
        "worker persistence is explicit and immutable"
    )


if __name__ == "__main__":
    main()
