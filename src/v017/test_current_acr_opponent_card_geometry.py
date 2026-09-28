from pathlib import Path
import json
import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)


GEOMETRY = json.loads(
    Path(
        "config/v017/geometry_maximized.json"
    ).read_text()
)

SIX_SEAT_FRAME = Path(
    "runtime/debug/"
    "v017_full_card_geometry_exact_20260924_200646/"
    "native_01.png"
)

TOP_FRAME = Path(
    "runtime/debug/"
    "v017_seat_top_geometry_20260924_200834/"
    "native_01.png"
)


def native(path):
    image = cv2.imread(str(path))
    assert image is not None, path

    assert image.shape[:2] == (
        2168,
        3456,
    ), (
        path,
        image.shape,
    )

    return image


def main():
    six = native(
        SIX_SEAT_FRAME
    )

    expected_six = (
        "seat_upper_left",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "seat_lower_left",
        "seat_mid_left",
    )

    for seat in expected_six:
        assert opponent_cards_visible(
            six,
            GEOMETRY["hole_cards"][seat],
        ) is True, seat

    assert opponent_cards_visible(
        six,
        GEOMETRY["hole_cards"]["seat_top"],
    ) is False

    top = native(
        TOP_FRAME
    )

    assert opponent_cards_visible(
        top,
        GEOMETRY["hole_cards"]["seat_top"],
    ) is True

    print("NATIVE 3456x2168 CARD GEOMETRY: PASS")
    print("SMALL-FRAME CONVERSION: ABSENT")
    print("CURRENT ACR OPPONENT CARD GEOMETRY: PASS")


if __name__ == "__main__":
    main()
