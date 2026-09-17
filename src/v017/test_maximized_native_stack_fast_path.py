from pathlib import Path
import json
import time

import cv2

from src.vision.stack_reader import (
    read_stack_native_fast,
)


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "pair_maximized.png"
)

GEOMETRY = (
    ROOT
    / "runtime/debug/v017_max_geometry"
    / "geometry_maximized_final.json"
)

EXPECTED = {
    "seat_top": 73.87,
    "seat_upper_right": 62.50,
    "seat_mid_right": 109.98,
    "seat_lower_right": 106.72,
    "hero": 55.62,
    "seat_lower_left": 75.57,
    "seat_mid_left": 65.24,
    "seat_upper_left": 20.45,
}


def main():
    image = cv2.imread(
        str(FRAME)
    )

    if image is None:
        raise AssertionError(
            f"missing frame: {FRAME}"
        )

    geometry = json.loads(
        GEOMETRY.read_text()
    )

    exact = 0
    start = time.perf_counter()

    for seat, expected in EXPECTED.items():
        rect = geometry[
            "stack_regions"
        ][seat]

        x = int(rect["x"])
        y = int(rect["y"])
        w = int(rect["width"])
        h = int(rect["height"])

        crop = image[
            y:y + h,
            x:x + w,
        ].copy()

        result = (
            read_stack_native_fast(
                crop
            )
        )

        observed = result.get(
            "stack_bb"
        )

        print(
            f"{seat:18s}",
            f"expected={expected:6.2f}",
            f"observed={str(observed):>6s}",
            f"mode={result.get('mode')}",
        )

        assert (
            result.get("mode")
            == "native_green_fast"
        )

        assert observed is not None

        assert abs(
            float(observed)
            - expected
        ) < 0.011, (
            f"{seat}: "
            f"expected={expected} "
            f"observed={observed}"
        )

        exact += 1

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000.0

    assert exact == 8

    print()
    print("exact=8/8")
    print(
        "sequential table ms=",
        round(elapsed, 1),
    )
    print(
        "V0.17 NATIVE GREEN FAST PATH: PASS"
    )


if __name__ == "__main__":
    main()
