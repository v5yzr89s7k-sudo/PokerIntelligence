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

# Native stack-text-band scheduling wake.
#
# Controlled physical simulation found legitimate quantitative stack
# transitions whose changed area is too compact for the existing
# whole-region gates. Their strong motion is localized in the actual
# native stack-text glyph band.
#
# This grants OCR scheduling only. It has no poker-semantic authority.
TEXT_BAND_Y0 = 100
TEXT_BAND_Y1 = 155
TEXT_BAND_STRONG_DIFF = 80
TEXT_BAND_STRONG_COUNT = 120
TEXT_BAND_LARGEST_COMPONENT = 60
TEXT_BAND_MIN_COMPONENT_HEIGHT = 15


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

    band_y0 = min(
        TEXT_BAND_Y0,
        difference.shape[0],
    )
    band_y1 = min(
        TEXT_BAND_Y1,
        difference.shape[0],
    )

    text_band = difference[
        band_y0:band_y1,
        :
    ]

    text_band_mask = (
        text_band
        > TEXT_BAND_STRONG_DIFF
    ).astype("uint8")

    text_band_strong_count = int(
        text_band_mask.sum()
    )

    # Canonical stack crops can be shorter than the optional
    # text-band coordinates. In that case there is no component
    # evidence to measure, and OpenCV must not receive an empty
    # image.
    if text_band_mask.size == 0:
        component_count = 1
        component_stats = None
        largest_component_area = 0
        largest_component_height = 0
    else:
        (
            component_count,
            _,
            component_stats,
            _,
        ) = cv2.connectedComponentsWithStats(
            text_band_mask,
            connectivity=8,
        )

        largest_component_area = 0
        largest_component_height = 0

        for component_index in range(
            1,
            component_count,
        ):
            _, _, _, height, area = (
                component_stats[
                    component_index
                ]
            )

            if int(area) > largest_component_area:
                largest_component_area = int(
                    area
                )
                largest_component_height = int(
                    height
                )

    text_band_wake = bool(
        text_band_strong_count
        >= TEXT_BAND_STRONG_COUNT
        and largest_component_area
        >= TEXT_BAND_LARGEST_COMPONENT
        and largest_component_height
        >= TEXT_BAND_MIN_COMPONENT_HEIGHT
    )

    wake = bool(
        broad_wake
        or compact_glyph_wake
        or text_band_wake
    )

    return StackMotion(
        changed_fraction=(
            changed_fraction
        ),
        mean_diff=mean_diff,
        max_diff=max_diff,
        wake=wake,
    )
