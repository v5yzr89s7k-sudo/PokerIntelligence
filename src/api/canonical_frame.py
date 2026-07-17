from typing import Optional, Tuple

import cv2


DEFAULT_CANONICAL_SIZE = (934, 696)


def canonical_size(
    geometry: Optional[dict] = None,
) -> Tuple[int, int]:
    """
    Return the canonical geometry size as (width, height).
    """

    geometry = geometry or {}
    table_size = geometry.get("table_size") or {}

    width = int(
        table_size.get(
            "width",
            geometry.get(
                "width",
                DEFAULT_CANONICAL_SIZE[0],
            ),
        )
    )

    height = int(
        table_size.get(
            "height",
            geometry.get(
                "height",
                DEFAULT_CANONICAL_SIZE[1],
            ),
        )
    )

    if width <= 0 or height <= 0:
        raise ValueError(
            f"invalid canonical frame size: {width}x{height}"
        )

    return width, height


def to_canonical_frame(
    frame,
    geometry: Optional[dict] = None,
):
    """
    Normalize an OpenCV frame to the geometry coordinate system.
    """

    if frame is None or frame.size == 0:
        raise ValueError(
            "frame must be a non-empty image"
        )

    target_width, target_height = canonical_size(
        geometry
    )

    frame_height, frame_width = frame.shape[:2]

    if (
        frame_width == target_width
        and frame_height == target_height
    ):
        return frame

    return cv2.resize(
        frame,
        (
            target_width,
            target_height,
        ),
        interpolation=cv2.INTER_AREA,
    )
