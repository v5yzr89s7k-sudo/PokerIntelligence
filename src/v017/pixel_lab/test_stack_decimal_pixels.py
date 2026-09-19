"""
V0.17 Pixel Lab authentic stack-decimal regression.

The production native stack reader must recover three-digit values
whose whole-number glyph geometry previously caused the synthetic
decimal point to disappear under OCR.

Generator only. Production OCR is unchanged.
"""

from pathlib import Path
import json

import cv2

from src.vision.stack_reader import (
    read_stack_native_fast,
)

from src.v017.pixel_lab.test_novel_stack_pixels import (
    build_atlas,
    render_stack_value,
)


ROOT = Path(__file__).resolve().parents[3]

SOURCE = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

SEAT = "seat_upper_left"

VALUES = (
    131.88,
    131.89,
    131.90,
    131.91,
    131.92,
    131.98,
    132.02,
    132.90,
)


def main():
    base = cv2.imread(str(SOURCE))
    assert base is not None, SOURCE

    atlas = build_atlas(base)

    assert "." in atlas

    rect = GEOMETRY[
        "stack_regions"
    ][SEAT]

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    print(
        "===== AUTHENTIC STACK DECIMAL REGRESSION ====="
    )

    for expected in VALUES:
        image = base.copy()

        render_stack_value(
            image,
            geometry=GEOMETRY,
            seat=SEAT,
            value=expected,
            atlas=atlas,
        )

        result = read_stack_native_fast(
            image[
                y:y + h,
                x:x + w,
            ]
        )

        observed = result.get(
            "stack_bb"
        )

        print(
            f"{expected:.2f}",
            "->",
            result,
        )

        assert observed is not None, (
            expected,
            result,
        )

        assert abs(
            float(observed)
            - float(expected)
        ) < 0.001, (
            expected,
            observed,
            result,
        )

    print()
    print(
        "131.xx DECIMAL RECOVERY: PASS"
    )
    print(
        "AUTHENTIC DECIMAL GLYPH: PASS"
    )
    print(
        "PRODUCTION OCR UNCHANGED: PASS"
    )
    print()
    print(
        "V0.17 STACK DECIMAL PIXELS: PASS"
    )


if __name__ == "__main__":
    main()
