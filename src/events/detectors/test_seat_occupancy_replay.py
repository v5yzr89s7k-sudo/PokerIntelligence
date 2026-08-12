import json
from pathlib import Path

import cv2

from src.events.detectors.seat_occupancy_detector import (
    seat_occupancy,
    occupied_seats,
)


ROOT = Path(__file__).resolve().parents[3]

FRAME = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222/0001_full.png"
)

GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


def main():
    image = cv2.imread(str(FRAME))

    if image is None:
        raise RuntimeError(
            f"Replay 0001 frame missing: {FRAME}"
        )

    image = cv2.resize(
        image,
        (934, 696),
    )

    results = seat_occupancy(
        image,
        GEOMETRY,
    )

    seats = occupied_seats(
        image,
        GEOMETRY,
    )

    expected = [
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
    ]

    assert results["seat_upper_left"]["occupied"] is True
    assert results["seat_upper_right"]["occupied"] is False
    assert seats == expected, (seats, expected)

    print(
        "PASS Replay 0001 occupancy: "
        "7 players, upper-left occupied, upper-right empty"
    )


if __name__ == "__main__":
    main()
