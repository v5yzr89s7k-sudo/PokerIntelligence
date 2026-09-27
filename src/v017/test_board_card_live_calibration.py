"""
Regression for the live v0.17 board-card presence calibration.

Measured production evidence:

    legitimate dark flop card:
        bright_ratio = 0.408676

    simultaneous empty turn:
        bright_ratio = 0.004809

    simultaneous empty river:
        bright_ratio = 0.001684

The former 0.45 aggregate-ratio threshold rejected the legitimate
flop card, causing production board count to remain at 2 and preventing
the physical PREFLOP -> FLOP boundary.

This regression proves the detector accepts the measured legitimate
class while retaining rejection of measured empty-board controls.
"""

from pathlib import Path

import cv2

from src.events.detectors.card_presence import (
    board_card_present,
)


ROOT = Path(
    "runtime/debug/v017_visible_flop_probe"
)


def read(name):
    path = ROOT / f"{name}.png"

    image = cv2.imread(str(path))

    assert image is not None, (
        f"missing calibration artifact: {path}"
    )

    return image


def main():
    flop_1 = read("flop_1")
    flop_2 = read("flop_2")
    flop_3 = read("flop_3")
    turn = read("turn")
    river = read("river")

    assert board_card_present(flop_1), (
        "dark legitimate flop_1 remains rejected"
    )

    assert board_card_present(flop_2)
    assert board_card_present(flop_3)

    assert not board_card_present(turn), (
        "empty turn became false positive"
    )

    assert not board_card_present(river), (
        "empty river became false positive"
    )

    observed = [
        board_card_present(image)
        for image in (
            flop_1,
            flop_2,
            flop_3,
            turn,
            river,
        )
    ]

    assert observed == [
        True,
        True,
        True,
        False,
        False,
    ], observed

    print(
        "V0.17 BOARD CARD LIVE CALIBRATION: PASS"
    )


if __name__ == "__main__":
    main()
