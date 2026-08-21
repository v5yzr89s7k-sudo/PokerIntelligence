from pathlib import Path

import cv2

from src.events.local_event_detector import (
    LocalEventDetector,
)

ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence"
    / "20260722_152155"
)


def read_frame(number):
    path = SESSION / f"{number:04d}_full.png"

    image = cv2.imread(str(path))

    if image is None:
        raise RuntimeError(
            f"could not read {path}"
        )

    return image


def main():
    detector = LocalEventDetector()

    detector.detect(
        read_frame(96)
    )

    changes = detector.detect(
        read_frame(97)
    )

    assert (
        "seat_lower_right"
        in changes.opponent_hole_card_changed_seats
    ), changes.to_dict()

    assert (
        "seat_lower_right"
        in changes.opponent_hole_cards_disappeared_seats
    ), changes.to_dict()

    print(
        "PASS physical opponent fold perception: "
        "calibrated card backs visible -> absent "
        "for seat_lower_right on consecutive raw frames"
    )


if __name__ == "__main__":
    main()
