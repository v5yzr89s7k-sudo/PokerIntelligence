"""
Generated opponent-card pixels must survive the exact production
native -> canonical sensor transformation.

This is a Pixel Lab rendering contract, not poker-semantic authority.
"""

from pathlib import Path

import cv2

from src.events.detectors.card_presence import (
    opponent_cards_visible,
)
from src.v017.run_live_observer import (
    canonical_sensor_frame,
    SENSOR_GEOMETRY,
)


ROOT = Path(__file__).resolve().parents[3]

FRAMES = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)

EXPECTED = {
    9: {
        "seat_mid_right": True,
        "seat_lower_right": True,
        "seat_upper_left": True,
        "seat_top": True,
        "seat_upper_right": True,
    },
    10: {
        "seat_mid_right": False,
        "seat_lower_right": True,
        "seat_upper_left": True,
        "seat_top": True,
        "seat_upper_right": True,
    },
    11: {
        "seat_mid_right": False,
        "seat_lower_right": False,
        "seat_upper_left": True,
        "seat_top": True,
        "seat_upper_right": True,
    },
    12: {
        "seat_mid_right": False,
        "seat_lower_right": False,
        "seat_upper_left": True,
        "seat_top": True,
        "seat_upper_right": True,
    },
    13: {
        "seat_mid_right": False,
        "seat_lower_right": False,
        "seat_upper_left": False,
        "seat_top": True,
        "seat_upper_right": True,
    },
    14: {
        "seat_mid_right": False,
        "seat_lower_right": False,
        "seat_upper_left": False,
        "seat_top": False,
        "seat_upper_right": True,
    },
}


def main():
    observed = {}

    for frame_id, expected in EXPECTED.items():
        path = (
            FRAMES
            / f"frame_{frame_id:04d}.png"
        )

        native = cv2.imread(str(path))
        assert native is not None, path

        sensor = canonical_sensor_frame(
            native
        )

        row = {}

        for seat in expected:
            row[seat] = bool(
                opponent_cards_visible(
                    sensor,
                    SENSOR_GEOMETRY[
                        "hole_cards"
                    ][seat],
                )
            )

        observed[frame_id] = row

        print(
            "frame",
            frame_id,
            "expected=",
            expected,
        )
        print(
            " " * 8,
            "observed=",
            row,
        )

    assert observed == EXPECTED, observed

    print(
        "CANONICAL ACQUISITION CARD STATE: PASS"
    )
    print(
        "CANONICAL FOLD TRANSITIONS: PASS"
    )
    print(
        "V0.17 PIXEL CANONICAL CARD TRANSITIONS: PASS"
    )


if __name__ == "__main__":
    main()
