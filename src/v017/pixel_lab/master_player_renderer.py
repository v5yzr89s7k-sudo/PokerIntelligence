"""
V0.17 master-backed controlled player renderer.

GENERATOR SIDE ONLY.

Responsibilities:
  * install the exact-native clean authentic ACR player plate for a seat;
  * render controlled visible player identity;
  * render controlled stack using authentic ACR stack glyphs;
  * claim seat_identity and stack ownership.

No semantic information is exposed to production.
"""

from pathlib import Path

import cv2

import json


_CANONICAL_GEOMETRY = None


def load_canonical_geometry():
    global _CANONICAL_GEOMETRY

    if _CANONICAL_GEOMETRY is None:
        root = Path(
            __file__
        ).resolve().parents[3]

        _CANONICAL_GEOMETRY = (
            json.loads(
                (
                    root
                    / "config/geometry.json"
                ).read_text()
            )
        )

    return _CANONICAL_GEOMETRY


from src.v017.pixel_lab.master_player_plates import (
    OUT as PLAYER_PLATES,
    plate_bounds,
)
from src.v017.pixel_lab.test_novel_stack_pixels import (
    render_stack_value,
)


def _clean_plate_path(
    seat,
):
    return (
        PLAYER_PLATES
        / f"{seat}_clean.png"
    )


def install_clean_plate(
    image,
    *,
    geometry,
    seat,
):
    path = _clean_plate_path(
        seat
    )

    plate = cv2.imread(
        str(path)
    )

    if plate is None:
        raise RuntimeError(
            f"missing clean player plate: {path}"
        )

    x1, y1, x2, y2 = (
        plate_bounds(
            geometry,
            seat,
        )
    )

    expected = (
        y2 - y1,
        x2 - x1,
    )

    if plate.shape[:2] != expected:
        raise RuntimeError(
            f"clean plate geometry mismatch "
            f"seat={seat} "
            f"expected={expected} "
            f"observed={plate.shape[:2]}"
        )

    image[
        y1:y2,
        x1:x2,
    ] = plate

    return (
        x1,
        y1,
        x2,
        y2,
    )


def render_player_name(
    image,
    *,
    geometry,
    seat,
    name,
):
    """
    Render identity in the authentic ACR name lane.

    The successful upper-left physical proof established the name lane
    as the upper text portion of the clean player plate. Use normalized
    coordinates inside each seat's own exact-native plate; never resize
    one seat's plate into another seat.
    """
    x1, y1, x2, y2 = (
        plate_bounds(
            geometry,
            seat,
        )
    )

    width = x2 - x1
    height = y2 - y1

    # Successful upper-left proof:
    #   clean plate height = 250
    #   accepted local name lane = 72:160
    #
    # Preserve that physical proportion per exact seat plate.
    lane_y1 = (
        y1
        + int(
            round(
                height
                * (72.0 / 250.0)
            )
        )
    )

    lane_y2 = (
        y1
        + int(
            round(
                height
                * (160.0 / 250.0)
            )
        )
    )

    # Identity pixels must fit inside BOTH:
    #
    #   1. the authentic native player plate, and
    #   2. the physical region consumed by production Snapshot V3.
    #
    # The native player plate can extend beyond the canonical
    # Snapshot seat card. Rendering against plate width alone can
    # therefore produce perfectly visible native text whose trailing
    # glyphs are absent from production's identity crop.
    #
    # canonical table: 934 x 696
    # native table:     3456 x 2168
    canonical_geometry = load_canonical_geometry()

    canonical_seat = (
        canonical_geometry[
            "seat_regions"
        ][seat]
    )

    native_table = geometry[
        "table_size"
    ]

    canonical_table = (
        canonical_geometry[
            "table_size"
        ]
    )

    scale_x = (
        float(native_table["width"])
        / float(canonical_table["width"])
    )

    snapshot_x1 = int(
        round(
            canonical_seat["x"]
            * scale_x
        )
    )

    snapshot_x2 = int(
        round(
            (
                canonical_seat["x"]
                + canonical_seat["width"]
            )
            * scale_x
        )
    )

    # Six canonical pixels of safety on each side. This protects
    # antialiased edge glyphs after native -> canonical reduction.
    safety = int(
        round(
            6.0 * scale_x
        )
    )

    snapshot_safe_x1 = (
        snapshot_x1 + safety
    )

    snapshot_safe_x2 = (
        snapshot_x2 - safety
    )

    # Production-visible name lane = intersection of authentic plate
    # and Snapshot's safely observable physical region.
    lane_x1 = max(
        x1,
        snapshot_safe_x1,
    )

    lane_x2 = min(
        x2,
        snapshot_safe_x2,
    )

    if lane_x2 <= lane_x1:
        raise RuntimeError(
            f"no production-visible name lane "
            f"seat={seat} "
            f"plate=({x1},{x2}) "
            f"snapshot_safe="
            f"({snapshot_safe_x1},"
            f"{snapshot_safe_x2})"
        )

    lane_w = lane_x2 - lane_x1
    lane_h = lane_y2 - lane_y1

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 3
    scale = 1.45

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
            tw <= lane_w - 12
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
        lane_x1
        + (lane_w - tw) // 2
    )

    ty = (
        lane_y1
        + (
            lane_h
            + th
            - baseline
        ) // 2
    )

    cv2.putText(
        image,
        str(name),
        (tx, ty),
        font,
        scale,
        (235, 238, 220),
        thickness,
        cv2.LINE_AA,
    )


def render_master_player(
    frame,
    *,
    seat,
    name,
    stack_bb,
    atlas,
):
    """
    Replace one master's stale player identity/stack with controlled
    physical evidence and claim exactly those ownership lanes.
    """
    image = frame.image
    geometry = frame.geometry

    install_clean_plate(
        image,
        geometry=geometry,
        seat=seat,
    )

    render_player_name(
        image,
        geometry=geometry,
        seat=seat,
        name=name,
    )

    render_stack_value(
        image,
        geometry=geometry,
        seat=seat,
        value=stack_bb,
        atlas=atlas,
    )

    frame.claim_seat_identity(
        seat
    )

    frame.claim_stack(
        seat
    )
