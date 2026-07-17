from pathlib import Path
from typing import Dict, List, Optional
import json

import cv2
import numpy as np

from src.api.canonical_frame import (
    to_canonical_frame,
)
from src.events.detectors.seat_occupancy_detector import (
    SEAT_ORDER,
    seat_occupancy,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GEOMETRY_PATH = ROOT / "config/geometry.json"


def load_geometry(path: Optional[Path] = None) -> dict:
    geometry_path = Path(
        path or DEFAULT_GEOMETRY_PATH
    )

    if not geometry_path.exists():
        raise FileNotFoundError(
            f"geometry file not found: {geometry_path}"
        )

    return json.loads(
        geometry_path.read_text()
    )


def _crop(frame, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    width = int(rect["width"])
    height = int(rect["height"])

    return frame[
        y:y + height,
        x:x + width,
    ]


def seat_card_bounds(
    seat: str,
    geometry: dict,
    frame_width: int,
    frame_height: int,
):
    """
    Return a crop centered on the seat nameplate and stack.

    The crop deliberately excludes most hole-card and table regions.
    """

    seat_rect = geometry["seat_regions"][seat]
    stack_rect = geometry["stack_regions"][seat]

    x1 = min(
        int(seat_rect["x"]),
        int(stack_rect["x"]),
    )
    y1 = min(
        int(seat_rect["y"]),
        int(stack_rect["y"]),
    )
    x2 = max(
        int(seat_rect["x"])
        + int(seat_rect["width"]),
        int(stack_rect["x"])
        + int(stack_rect["width"]),
    )
    y2 = max(
        int(seat_rect["y"])
        + int(seat_rect["height"]),
        int(stack_rect["y"])
        + int(stack_rect["height"]),
    )

    x_margin = 24
    top_margin = 58
    bottom_margin = 12

    return (
        max(0, x1 - x_margin),
        max(0, y1 - top_margin),
        min(frame_width, x2 + x_margin),
        min(frame_height, y2 + bottom_margin),
    )


def build_seat_cards(
    frame,
    geometry: Optional[dict] = None,
    occupied_only: bool = True,
) -> List[Dict]:
    """
    Build deterministic physical-seat crops.

    Each returned item contains:
      - immutable seat ID
      - local occupancy result
      - crop bounds
      - crop image

    GPT or OCR must never be allowed to change the seat ID.
    """

    if frame is None or frame.size == 0:
        raise ValueError(
            "frame must be a non-empty image"
        )

    geometry = geometry or load_geometry()

    frame = to_canonical_frame(
        frame,
        geometry,
    )

    occupancy = seat_occupancy(
        frame,
        geometry,
    )

    height, width = frame.shape[:2]
    cards = []

    for seat in SEAT_ORDER:
        occupancy_result = occupancy[seat]

        if (
            occupied_only
            and not occupancy_result["occupied"]
        ):
            continue

        x1, y1, x2, y2 = seat_card_bounds(
            seat,
            geometry,
            frame_width=width,
            frame_height=height,
        )

        crop = frame[y1:y2, x1:x2].copy()

        if crop.size == 0:
            raise RuntimeError(
                f"empty seat-card crop for {seat}"
            )

        cards.append({
            "seat": seat,
            "occupied": bool(
                occupancy_result["occupied"]
            ),
            "occupancy_confidence": float(
                occupancy_result["confidence"]
            ),
            "bounds": {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            },
            "image": crop,
        })

    return cards


def build_seat_card_montage(
    seat_cards: List[Dict],
    scale: float = 2.0,
):
    if not seat_cards:
        raise ValueError(
            "seat_cards must not be empty"
        )

    panels = []

    for item in seat_cards:
        crop = item["image"]

        enlarged = cv2.resize(
            crop,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

        label_height = 50
        panel_width = max(
            enlarged.shape[1],
            430,
        )

        panel = np.zeros(
            (
                label_height
                + enlarged.shape[0],
                panel_width,
                3,
            ),
            dtype=np.uint8,
        )

        panel[
            label_height:
            label_height + enlarged.shape[0],
            0:enlarged.shape[1],
        ] = enlarged

        label = (
            f"{item['seat']} | "
            f"occupied={item['occupied']} | "
            f"confidence="
            f"{item['occupancy_confidence']:.2f}"
        )

        cv2.putText(
            panel,
            label,
            (8, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        panels.append(panel)

    columns = 2
    rows = []

    for start in range(
        0,
        len(panels),
        columns,
    ):
        group = panels[
            start:start + columns
        ]

        if len(group) == 1:
            blank = np.zeros_like(group[0])
            group.append(blank)

        row_height = max(
            panel.shape[0]
            for panel in group
        )

        normalized = []

        for panel in group:
            if panel.shape[0] < row_height:
                vertical_pad = np.zeros(
                    (
                        row_height - panel.shape[0],
                        panel.shape[1],
                        3,
                    ),
                    dtype=np.uint8,
                )
                panel = np.vstack([
                    panel,
                    vertical_pad,
                ])

            normalized.append(panel)

        rows.append(
            np.hstack(normalized)
        )

    max_width = max(
        row.shape[1]
        for row in rows
    )

    normalized_rows = []

    for row in rows:
        if row.shape[1] < max_width:
            horizontal_pad = np.zeros(
                (
                    row.shape[0],
                    max_width - row.shape[1],
                    3,
                ),
                dtype=np.uint8,
            )
            row = np.hstack([
                row,
                horizontal_pad,
            ])

        normalized_rows.append(row)

    return np.vstack(normalized_rows)
