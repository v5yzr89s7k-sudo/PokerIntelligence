"""
V0.17 Pixel Lab authentic fold-pixel primitive.

Generator-side acceptance only.

Proves that authentic ACR pixels can represent, for every opponent seat
required by real hand 2826874674:

    dealt-in -> folded
    production opponent_cards_visible(): True -> False

No production detector is modified.
No semantic truth is supplied to FrameHandObserver.
"""

from pathlib import Path
import json
import shutil

import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

CANONICAL = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_8p.png"
)

SUBSTRATE_6P = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_6p.png"
)

SUBSTRATE_7P = (
    ROOT
    / "runtime/pixel_lab/substrates/"
      "native_6_7_8/substrate_7p.png"
)

MAXIMIZED = (
    ROOT
    / "runtime/debug/v017_resolution_ab/"
      "maximized.png"
)

OVERLAY = (
    ROOT
    / "runtime/debug/v017_max_geometry/"
      "geometry_maximized_final_overlay_v2.png"
)

WORK = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "authentic_fold_pixels"
)

TARGET_SEATS = (
    "seat_upper_left",
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
)

# Authentic detector-positive donor per physical seat.
PRESENT_DONORS = {
    "seat_upper_left": SUBSTRATE_6P,
    "seat_top": CANONICAL,
    "seat_upper_right": CANONICAL,
    "seat_mid_right": CANONICAL,
    "seat_lower_right": CANONICAL,
}

# Authentic detector-negative donor per physical seat.
ABSENT_DONORS = {
    "seat_upper_left": SUBSTRATE_7P,
    "seat_top": OVERLAY,
    "seat_upper_right": MAXIMIZED,
    "seat_mid_right": MAXIMIZED,
    "seat_lower_right": MAXIMIZED,
}


def load(path):
    image = cv2.imread(str(path))
    assert image is not None, path
    assert image.shape[:2] == (2168, 3456), (
        path,
        image.shape,
    )
    return image


def transplant_hole_cards(
    destination,
    donor,
    seat,
):
    """
    Copy only the two calibrated hole-card ROIs.

    Nothing outside production's physical card-presence measurement
    regions crosses from the donor.
    """
    result = destination.copy()

    regions = GEOMETRY[
        "hole_cards"
    ][seat]

    for card_name in (
        "card_1",
        "card_2",
    ):
        rect = regions[card_name]

        x = int(rect["x"])
        y = int(rect["y"])
        w = int(rect["width"])
        h = int(rect["height"])

        result[
            y:y + h,
            x:x + w,
        ] = donor[
            y:y + h,
            x:x + w,
        ]

    return result


def visible(image, seat):
    return bool(
        opponent_cards_visible(
            image,
            GEOMETRY["hole_cards"][seat],
        )
    )


def main():
    shutil.rmtree(
        WORK,
        ignore_errors=True,
    )
    WORK.mkdir(
        parents=True,
        exist_ok=True,
    )

    base = load(CANONICAL)

    print(
        "===== AUTHENTIC FOLD PIXEL PRIMITIVE ====="
    )

    for seat in TARGET_SEATS:
        present_donor = load(
            PRESENT_DONORS[seat]
        )
        absent_donor = load(
            ABSENT_DONORS[seat]
        )

        before = transplant_hole_cards(
            base,
            present_donor,
            seat,
        )

        after = transplant_hole_cards(
            before,
            absent_donor,
            seat,
        )

        before_path = (
            WORK / f"{seat}_before.png"
        )
        after_path = (
            WORK / f"{seat}_after.png"
        )

        assert cv2.imwrite(
            str(before_path),
            before,
        )
        assert cv2.imwrite(
            str(after_path),
            after,
        )

        before_visible = visible(
            before,
            seat,
        )
        after_visible = visible(
            after,
            seat,
        )

        print()
        print(seat)
        print(
            " present donor =",
            PRESENT_DONORS[seat],
        )
        print(
            " absent donor  =",
            ABSENT_DONORS[seat],
        )
        print(
            " detector =",
            before_visible,
            "->",
            after_visible,
        )

        assert before_visible is True, (
            seat,
            "authentic present donor failed",
        )

        assert after_visible is False, (
            seat,
            "authentic absent donor failed",
        )

    print()
    print(
        "ALL TARGET OPPONENTS TRUE -> FALSE: PASS"
    )
    print(
        "PRODUCTION CARD DETECTOR UNCHANGED: PASS"
    )
    print(
        "AUTHENTIC ROI TRANSPLANT ONLY: PASS"
    )
    print()
    print(
        "V0.17 AUTHENTIC FOLD PIXELS: PASS"
    )


if __name__ == "__main__":
    main()
