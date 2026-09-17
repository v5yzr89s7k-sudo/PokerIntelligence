from pathlib import Path
import json

import cv2

from src.v017.native_seat_occupancy import (
    native_seat_occupancy,
    native_occupied_seats,
)


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/window_captures"
    / "acr_table_20260917_151525_804165.png"
)

GEOMETRY = (
    ROOT
    / "config/v017/geometry_maximized.json"
)

EXPECTED = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_mid_left",
]


def main():
    image = cv2.imread(
        str(FRAME)
    )

    if image is None:
        raise AssertionError(
            f"missing live frame: {FRAME}"
        )

    geometry = json.loads(
        GEOMETRY.read_text()
    )

    details = native_seat_occupancy(
        image,
        geometry,
    )

    occupied = native_occupied_seats(
        image,
        geometry,
    )

    print(
        "===== SIX-PLAYER LIVE OCCUPANCY ====="
    )

    for seat, row in details.items():
        print(
            f"{seat:18s}",
            "present=",
            row["present"],
            "raw=",
            repr(row["raw"]),
        )

    print()
    print(
        "occupied =",
        occupied,
    )

    assert occupied == EXPECTED, (
        f"expected={EXPECTED} "
        f"observed={occupied}"
    )

    assert (
        details[
            "seat_mid_left"
        ]["present"]
        is True
    )

    assert (
        "16.68"
        in details[
            "seat_mid_left"
        ]["raw"]
    )

    # Empty physical seats must remain absent.
    assert (
        details[
            "seat_lower_left"
        ]["present"]
        is False
    )

    assert (
        details[
            "seat_upper_left"
        ]["present"]
        is False
    )

    print()
    print(
        "V0.17 SIX-PLAYER NATIVE OCCUPANCY: PASS"
    )


if __name__ == "__main__":
    main()
