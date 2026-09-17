"""
V0.17 maximized-native seat occupancy.

Occupancy authority and quantitative stack authority are deliberately
separate.

A recognizable numeric stack line containing BB establishes physical
seat presence. It does NOT establish a trustworthy quantitative stack
value.
"""

import re

import cv2
import pytesseract


LOWER_GREEN = (35, 30, 60)
UPPER_GREEN = (95, 255, 255)

SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]


def _crop(frame, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    return frame[
        y:y + h,
        x:x + w,
    ].copy()


def stack_text_presence(crop):
    if crop is None or crop.size == 0:
        return {
            "present": False,
            "raw": "",
            "green_ratio": 0.0,
        }

    hsv = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2HSV,
    )

    green = cv2.inRange(
        hsv,
        LOWER_GREEN,
        UPPER_GREEN,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2, 2),
    )

    green = cv2.morphologyEx(
        green,
        cv2.MORPH_OPEN,
        kernel,
    )

    green = cv2.morphologyEx(
        green,
        cv2.MORPH_CLOSE,
        kernel,
    )

    raw = pytesseract.image_to_string(
        green,
        config="--psm 7",
    ).strip()

    has_number = bool(
        re.search(
            r"\d",
            raw,
        )
    )

    has_bb = bool(
        re.search(
            r"\bBB\b",
            raw,
            re.IGNORECASE,
        )
    )

    # Occupancy authority is intentionally weaker than
    # quantitative stack authority.
    #
    # Native OCR can preserve a clear decimal stack number while
    # mangling or dropping the trailing BB glyphs, e.g.
    # "16.6888". That is still strong evidence that the seat is
    # physically occupied, but it must NOT promote the numeric
    # value to trusted stack authority.
    has_decimal_stack = bool(
        re.search(
            r"\d+\.\d+",
            raw,
        )
    )

    return {
        "present": bool(
            has_number
            and (
                has_bb
                or has_decimal_stack
            )
        ),
        "raw": raw,
        "green_ratio": float(
            (green > 0).mean()
        ),
    }


def native_seat_occupancy(
    frame,
    geometry,
):
    results = {}

    for seat in SEAT_ORDER:
        crop = _crop(
            frame,
            geometry[
                "stack_regions"
            ][seat],
        )

        results[seat] = (
            stack_text_presence(
                crop
            )
        )

    return results


def native_occupied_seats(
    frame,
    geometry,
):
    results = native_seat_occupancy(
        frame,
        geometry,
    )

    return [
        seat
        for seat in SEAT_ORDER
        if results[seat]["present"]
    ]
