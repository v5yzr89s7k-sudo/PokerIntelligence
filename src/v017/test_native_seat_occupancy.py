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
    / "acr_table_20260917_125439_191149.png"
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
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]


def main():
    image = cv2.imread(
        str(FRAME)
    )

    if image is None:
        raise AssertionError(
            f"missing live frame: {FRAME}"
        )

    assert (
        image.shape[1],
        image.shape[0],
    ) == (
        3456,
        2168,
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
        "===== NATIVE OCCUPANCY ====="
    )

    for seat in EXPECTED:
        row = details[seat]

        print(
            f"{seat:18s}",
            "present=",
            row["present"],
            "raw=",
            repr(row["raw"]),
        )

        assert row["present"]

    assert occupied == EXPECTED, (
        f"expected={EXPECTED} "
        f"observed={occupied}"
    )

    # These two are important: integer stacks prove that
    # occupancy does not depend on quantitative decimal
    # stack authority.
    assert "85 BB" in (
        details[
            "seat_mid_left"
        ]["raw"]
    )

    assert "85 BB" in (
        details[
            "seat_upper_left"
        ]["raw"]
    )

    print()
    print("occupied=8/8")
    print(
        "V0.17 NATIVE SEAT OCCUPANCY: PASS"
    )


if __name__ == "__main__":
    main()
