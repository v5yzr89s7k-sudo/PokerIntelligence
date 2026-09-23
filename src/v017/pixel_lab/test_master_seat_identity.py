"""
Bounded physical proof for master-backed seat identity.

Generator side constructs ONE controlled seat.
Production Snapshot V3 independently reads the resulting physical crop.
"""

from pathlib import Path
import json

import cv2
import numpy as np

from src.v017.pixel_lab.master_frame import (
    load_master_copy,
)
from src.v017.pixel_lab.test_novel_stack_pixels import (
    build_atlas,
    render_stack_value,
)


ROOT = Path(__file__).resolve().parents[3]

GEOMETRY = json.loads(
    (
        ROOT
        / "config/v017/"
          "geometry_maximized.json"
    ).read_text()
)

OUT_DIR = (
    ROOT
    / "runtime/pixel_lab/generator_work/"
      "master_seat_identity_probe"
)

SEAT = "seat_upper_left"
NAME = "The_Stranger"
STACK = 103.72


def render_name(
    image,
    *,
    seat,
    name,
):
    """
    Own the exact non-overlapping name lane:

        seat_region.y <= name lane < stack_region.y

    Production seat/stack ROIs intentionally overlap. They are detector
    geometry, not visual-component boundaries.

    No master-hand name pixels may survive in this lane.
    """
    seat_rect = GEOMETRY[
        "seat_regions"
    ][seat]

    stack_rect = GEOMETRY[
        "stack_regions"
    ][seat]

    seat_x = int(seat_rect["x"])
    seat_y = int(seat_rect["y"])
    seat_w = int(seat_rect["width"])

    stack_y = int(
        stack_rect["y"]
    )

    # Exact native non-overlap interval.
    name_y1 = seat_y
    name_y2 = stack_y

    if name_y2 <= name_y1:
        raise RuntimeError(
            f"invalid name lane for {seat}: "
            f"{name_y1}:{name_y2}"
        )

    # Preserve a very small horizontal edge of the authentic plate.
    x1 = seat_x + 4
    x2 = (
        seat_x
        + seat_w
        - 4
    )

    # Obtain dark authentic plate pixels from the same lane.
    lane = image[
        name_y1:name_y2,
        x1:x2,
    ].copy()

    gray = cv2.cvtColor(
        lane,
        cv2.COLOR_BGR2GRAY,
    )

    hsv = cv2.cvtColor(
        lane,
        cv2.COLOR_BGR2HSV,
    )

    # Exclude the existing cream player-name glyphs and bright borders.
    valid_mask = (
        (gray >= 20)
        & (gray <= 120)
        & (hsv[:, :, 1] <= 120)
    )

    samples = lane[
        valid_mask
    ]

    if len(samples) < 100:
        raise RuntimeError(
            f"insufficient authentic nameplate "
            f"background for {seat}"
        )

    background = np.median(
        samples,
        axis=0,
    ).astype(np.uint8)

    # FULL OWNERSHIP.
    image[
        name_y1:name_y2,
        x1:x2,
    ] = background

    lane_w = x2 - x1
    lane_h = name_y2 - name_y1

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 3
    scale = 1.35

    while scale >= 0.30:
        (tw, th), baseline = (
            cv2.getTextSize(
                name,
                font,
                scale,
                thickness,
            )
        )

        if (
            tw <= lane_w - 20
            and th + baseline
            <= lane_h - 10
        ):
            break

        scale -= 0.025

    (tw, th), baseline = (
        cv2.getTextSize(
            name,
            font,
            scale,
            thickness,
        )
    )

    tx = (
        x1
        + (lane_w - tw) // 2
    )

    ty = (
        name_y1
        + (
            lane_h
            + th
            - baseline
        ) // 2
    )

    cv2.putText(
        image,
        name,
        (tx, ty),
        font,
        scale,
        (235, 238, 220),
        thickness,
        cv2.LINE_AA,
    )

    return {
        "seat": seat,
        "name_lane_native": {
            "x": x1,
            "y": name_y1,
            "width": lane_w,
            "height": lane_h,
        },
    }


def main():
    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    image = load_master_copy()

    # Build the authentic stack glyph atlas BEFORE changing the frame.
    atlas = build_atlas(
        image
    )

    render_name(
        image,
        seat=SEAT,
        name=NAME,
    )

    render_stack_value(
        image,
        geometry=GEOMETRY,
        seat=SEAT,
        value=STACK,
        atlas=atlas,
    )

    output = (
        OUT_DIR
        / "seat_upper_left_"
          "The_Stranger_103.72.png"
    )

    assert cv2.imwrite(
        str(output),
        image,
    )

    print(
        "output =",
        output,
    )


if __name__ == "__main__":
    main()
