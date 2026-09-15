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

    wake = bool(
        changed_fraction
        >= WAKE_CHANGED_FRACTION
        and mean_diff
        >= WAKE_MEAN_DIFF
    )

    return StackMotion(
        changed_fraction=(
            changed_fraction
        ),
        mean_diff=mean_diff,
        max_diff=max_diff,
        wake=wake,
    )
