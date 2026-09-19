"""
V0.17 compact stack-motion wake regression.

The real ACR Pixel Lab hand contains a legitimate BB preflop call whose
visible stack changes:

    96.64 BB -> 95.04 BB

Only a compact subset of glyph pixels changes. The cheap motion
scheduler must wake OCR for this transition.

Wake remains non-semantic. This test grants no HandEngine authority.
"""

from pathlib import Path
import json

import cv2

from src.v017.stack_motion_gate import (
    measure_stack_motion,
)
from src.vision.stack_reader import (
    read_stack_native_fast,
)


ROOT = Path(__file__).resolve().parents[3]

BASE = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "real_acr_hand_2826874674"
)

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/geometry_maximized.json"
    ).read_text()
)

SEAT = "seat_upper_right"


def stack_read(image):
    r = GEOMETRY[
        "stack_regions"
    ][SEAT]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return read_stack_native_fast(
        image[
            y:y + h,
            x:x + w,
        ]
    )


def main():
    before = cv2.imread(
        str(
            BASE / "frame_0014.png"
        )
    )
    after = cv2.imread(
        str(
            BASE / "frame_0015.png"
        )
    )

    assert before is not None
    assert after is not None

    before_read = stack_read(before)
    after_read = stack_read(after)

    assert before_read["stack_bb"] == 96.64
    assert after_read["stack_bb"] == 95.04

    motion = measure_stack_motion(
        before,
        after,
        GEOMETRY,
        SEAT,
    )

    print(
        "===== COMPACT STACK MOTION WAKE ====="
    )
    print(
        "before =",
        before_read,
    )
    print(
        "after =",
        after_read,
    )
    print(
        "motion =",
        motion,
    )

    assert motion.wake, motion

    assert (
        motion.changed_fraction < 0.05
    ), (
        "fixture no longer exercises compact "
        "secondary wake",
        motion,
    )

    print()
    print(
        "REAL BB 96.64 -> 95.04: PASS"
    )
    print(
        "COMPACT GLYPH MOTION WAKES OCR: PASS"
    )
    print(
        "SEMANTIC AUTHORITY GRANTED: NO"
    )
    print()
    print(
        "V0.17 COMPACT STACK MOTION: PASS"
    )


if __name__ == "__main__":
    main()
