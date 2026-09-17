from pathlib import Path
import json

import cv2

from src.bootstrap.hero_bootstrap import (
    bootstrap_local_stacks,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/window_captures"
    / "acr_table_20260917_125439_191149.png"
)

GEOMETRY_PATH = (
    ROOT
    / "config/v017/geometry_maximized.json"
)

EXPECTED = {
    "hero": 80.43,
    "seat_lower_left": 97.02,
    "seat_lower_right": 97.81,
    "seat_mid_left": None,
    "seat_mid_right": 82.14,
    "seat_top": 79.62,
    "seat_upper_left": None,
    "seat_upper_right": 120.53,
}


def crop_geometry_region(
    image,
    rect,
):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    return image[
        y:y + h,
        x:x + w,
    ].copy()


def main():
    image = cv2.imread(
        str(FRAME)
    )

    if image is None:
        raise AssertionError(
            f"missing frame: {FRAME}"
        )

    assert (
        image.shape[1],
        image.shape[0],
    ) == (
        3456,
        2168,
    )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    rows = bootstrap_local_stacks(
        canonical_image=image,
        frozen_participants=list(
            EXPECTED.keys()
        ),
        geometry=geometry,
        crop_geometry_region=
            crop_geometry_region,
        stack_reader=
            read_stack_native_fast,
    )

    by_seat = {
        row["seat"]: row
        for row in rows
    }

    print(
        "===== NATIVE BOOTSTRAP AUTHORITY ====="
    )

    resolved = 0
    unresolved = 0

    for seat, expected in EXPECTED.items():
        row = by_seat[seat]

        observed = row.get(
            "stack_bb"
        )

        print(
            f"{seat:18s}",
            f"expected={str(expected):>6s}",
            f"observed={str(observed):>6s}",
        )

        if expected is None:
            assert observed is None, (
                seat,
                row,
            )
            unresolved += 1
            continue

        assert observed is not None, (
            seat,
            row,
        )

        assert abs(
            float(observed)
            - expected
        ) < 0.011, (
            seat,
            expected,
            observed,
        )

        resolved += 1

    assert resolved == 6
    assert unresolved == 2

    print()
    print(
        "resolved=6 unresolved=2"
    )
    print(
        "V0.17 NATIVE BOOTSTRAP STACK AUTHORITY: PASS"
    )


if __name__ == "__main__":
    main()
