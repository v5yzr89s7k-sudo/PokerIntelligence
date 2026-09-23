from pathlib import Path

import cv2

from src.v017.run_live_observer import (
    build_observer_from_frame,
    GEOMETRY,
)
from src.v017.stack_motion_gate import (
    measure_stack_motion,
)


ROOT = Path(__file__).resolve().parents[3]

BASE = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "controlled_hand_2826921615"
)

PARTICIPANTS = (
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
)

AUTHORITY = {
    "seat_top": 44.83,
    "seat_upper_right": 57.43,
    "seat_mid_right": 135.95,
    "seat_lower_right": 59.18,
    "hero": 21.41,
    "seat_lower_left": 179.63,
    "seat_mid_left": 116.22,
    "seat_upper_left": 48.76,
}


def main():
    p12 = BASE / "frame_0012.png"
    p13 = BASE / "frame_0013.png"

    f12 = cv2.imread(str(p12))
    f13 = cv2.imread(str(p13))

    assert f12 is not None
    assert f13 is not None

    observer = build_observer_from_frame(
        f12,
        p12,
        hand_id="native-acquisition-baseline",
        frozen_participants=PARTICIPANTS,
        frozen_stack_authority=AUTHORITY,
    )

    assert observer is not None

    print(
        "previous_frame_is_none =",
        observer.previous_frame is None,
    )

    assert observer.previous_frame is not None

    assert (
        observer.previous_frame.shape
        == f12.shape
    )

    motion = measure_stack_motion(
        observer.previous_frame,
        f13,
        GEOMETRY,
        "seat_top",
    )

    print(
        "motion_12_to_13 =",
        motion,
    )

    assert motion.wake

    assert abs(
        observer.trusted_stacks[
            "seat_top"
        ]
        - 44.83
    ) < 0.001

    print()
    print(
        "ACQUISITION NATIVE STACK BASELINE: PASS"
    )


if __name__ == "__main__":
    main()
