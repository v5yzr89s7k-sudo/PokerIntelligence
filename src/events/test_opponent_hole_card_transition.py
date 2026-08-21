from pathlib import Path

import cv2

from src.events.local_event_detector import (
    LocalEventDetector,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260722_152155"
)


def read(frame):
    path = (
        SESSION
        / f"{frame:04d}_full.png"
    )

    img = cv2.imread(str(path))

    if img is None:
        raise RuntimeError(
            f"cannot read {path}"
        )

    return img


def main():
    detector = LocalEventDetector()

    # Establish frame 96 as the detector's consecutive raw baseline.
    detector.detect(
        read(96)
    )

    changes = detector.detect(
        read(97)
    )

    seats = set(
        getattr(
            changes,
            "opponent_hole_card_changed_seats",
            [],
        )
    )

    assert (
        "seat_lower_right"
        in seats
    ), seats

    print(
        "PASS opponent-card transition: "
        "July 22 frame 096->097 retains BTN fold transition"
    )


if __name__ == "__main__":
    main()
