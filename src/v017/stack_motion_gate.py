"""
Cheap stack-region motion gate.

Purpose:
    Decide whether a stack region changed enough that targeted
    recognition may be worthwhile.

This module:
    - performs no OCR
    - assigns no poker semantics
    - mutates no HandEngine state
"""

from dataclasses import dataclass

import cv2


PIXEL_DIFF_THRESHOLD = 18

# Deliberately below the weakest known real July22 quantitative
# transition (Hero preflop = 0.0917), while remaining far above
# ordinary quiet-region motion.
WAKE_CHANGED_FRACTION = 0.05
WAKE_MEAN_DIFF = 4.0

# Secondary OCR-scheduling wake for compact stack-text changes.
#
# Some legitimate quantitative transitions alter only a few glyphs
# inside the relatively large calibrated stack ROI. Their changed
# fraction can therefore be far below the broad-motion threshold even
# though the changed glyph pixels have strong contrast.
#
# This remains perception scheduling only. A secondary wake does not
# update trusted stacks and has no poker-semantic authority; OCR,
# prior-aware resolution, settlement, and HandEngine admission remain
# unchanged downstream.
SECONDARY_CHANGED_FRACTION = 0.007
SECONDARY_MEAN_DIFF = 0.80
SECONDARY_MAX_DIFF = 180


@dataclass(frozen=True)
class StackMotion:
    changed_fraction: float
    mean_diff: float
    max_diff: int
    wake: bool


def stack_region_crop(
    frame,
    geometry,
    seat,
):
    rect = (
        geometry["stack_regions"]
        [seat]
    )

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    return frame[
        y:y + h,
        x:x + w,
    ]


def measure_stack_motion(
    previous_frame,
    current_frame,
    geometry,
    seat,
):
    before = stack_region_crop(
        previous_frame,
        geometry,
        seat,
    )

    after = stack_region_crop(
        current_frame,
        geometry,
        seat,
    )

    if (
        before.size == 0
        or after.size == 0
    ):
        raise ValueError(
            f"empty stack crop: {seat}"
        )

    before_gray = cv2.cvtColor(
        before,
        cv2.COLOR_BGR2GRAY,
    )

    after_gray = cv2.cvtColor(
        after,
        cv2.COLOR_BGR2GRAY,
    )

    difference = cv2.absdiff(
        before_gray,
        after_gray,
    )

    changed_fraction = float(
        (
            difference
            > PIXEL_DIFF_THRESHOLD
        ).mean()
    )

    mean_diff = float(
        difference.mean()
    )

    max_diff = int(
        difference.max()
    )

    broad_wake = bool(
        changed_fraction
        >= WAKE_CHANGED_FRACTION
        and mean_diff
        >= WAKE_MEAN_DIFF
    )

    compact_glyph_wake = bool(
        changed_fraction
        >= SECONDARY_CHANGED_FRACTION
        and mean_diff
        >= SECONDARY_MEAN_DIFF
        and max_diff
        >= SECONDARY_MAX_DIFF
    )

    wake = bool(
        broad_wake
        or compact_glyph_wake
    )

    return StackMotion(
        changed_fraction=(
            changed_fraction
        ),
        mean_diff=mean_diff,
        max_diff=max_diff,
        wake=wake,
    )
