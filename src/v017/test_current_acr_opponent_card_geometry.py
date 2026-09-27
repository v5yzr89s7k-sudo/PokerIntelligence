from pathlib import Path
import json
import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)
from src.v017.run_live_observer import (
    canonical_sensor_frame,
)


GEOMETRY = json.loads(
    Path("config/geometry.json").read_text()
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


def canonical(path):
    image = cv2.imread(str(path))

    assert image is not None, path

    return canonical_sensor_frame(
        image
    )


def main():
    six = canonical(
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

    print(
        "===== SIX-SEAT CALIBRATION FRAME ====="
    )

    for seat in expected_six:
        visible = opponent_cards_visible(
            six,
            GEOMETRY["hole_cards"][seat],
        )

        print(
            seat,
            "visible=",
            visible,
        )

        assert visible is True, seat

    # seat_top visibly had no cards in this frame.
    top_absent = opponent_cards_visible(
        six,
        GEOMETRY["hole_cards"]["seat_top"],
    )

    print(
        "seat_top visible=",
        top_absent,
        "(expected absent on this frame)",
    )

    assert top_absent is False

    print()
    print(
        "===== TOP-SEAT CALIBRATION FRAME ====="
    )

    top = canonical(
        TOP_FRAME
    )

    top_visible = opponent_cards_visible(
        top,
        GEOMETRY["hole_cards"]["seat_top"],
    )

    print(
        "seat_top visible=",
        top_visible,
    )

    assert top_visible is True

    print()
    print(
        "CURRENT ACR OPPONENT CARD GEOMETRY: PASS"
    )


if __name__ == "__main__":
    main()
