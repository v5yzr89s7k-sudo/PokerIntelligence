from pathlib import Path
import json

import cv2

from src.vision.stack_reader import read_stack


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

# Manually verified ground truth from the exact saved
# 3456x2168 maximized frame.
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


def crop_region(image, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    crop = image[
        y:y + h,
        x:x + w,
    ].copy()

    if crop.size == 0:
        raise AssertionError(
            f"empty crop: {rect}"
        )

    return crop


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

    assert (
        image.shape[1],
        image.shape[0],
    ) == (
        3456,
        2168,
    )

    print(
        "===== MAXIMIZED NATIVE STACK GROUND TRUTH ====="
    )

    passed = 0

    for seat, expected in EXPECTED.items():
        rect = geometry[
            "stack_regions"
        ][seat]

        crop = crop_region(
            image,
            rect,
        )

        result = read_stack(
            crop
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

        assert observed is not None, (
            f"{seat}: unresolved; "
            f"expected={expected}"
        )

        assert abs(
            float(observed)
            - float(expected)
        ) < 0.011, (
            f"{seat}: "
            f"expected={expected} "
            f"observed={observed} "
            f"raw={result.get('raw')}"
        )

        passed += 1

    assert passed == 8

    print()
    print(
        f"exact={passed}/8"
    )
    print(
        "V0.17 MAXIMIZED NATIVE STACK READER: PASS"
    )


if __name__ == "__main__":
    main()
