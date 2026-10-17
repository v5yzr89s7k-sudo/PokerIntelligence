from pathlib import Path

import cv2

from src.v017.native_dealer_detector import (
    detect_native_dealer,
)


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/validation/native_dealer/"
      "seat_mid_left.png"
)


def main():
    image = cv2.imread(str(FRAME))
    assert image is not None, FRAME

    result = detect_native_dealer(image)

    print("result =", result)

    assert result["confidence"] >= 0.85

    assert result["dealer_button_seat"] == (
        "seat_mid_left"
    )

    assert result["owners"] == [
        ("seat_mid_left", 0)
    ]

    assert abs(
        result["center_x"] - 905.5
    ) <= 3.0

    assert abs(
        result["center_y"] - 1206.0
    ) <= 3.0

    print(
        "NATIVE DEALER LOCALIZATION: PASS"
    )


if __name__ == "__main__":
    main()
