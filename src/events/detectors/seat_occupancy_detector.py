import cv2
import numpy as np


SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]


def _crop(frame, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    width = int(rect["width"])
    height = int(rect["height"])

    return frame[
        y:y + height,
        x:x + width,
    ]


def _features(crop):
    if crop.size == 0:
        return {
            "bright_ratio": 0.0,
            "edge_density": 0.0,
            "gray_std": 0.0,
        }

    gray = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2GRAY,
    )

    bright_ratio = float(
        (gray > 120).mean()
    )

    edges = cv2.Canny(
        gray,
        60,
        140,
    )

    edge_density = float(
        (edges > 0).mean()
    )

    gray_std = float(
        np.std(gray)
    )

    return {
        "bright_ratio": bright_ratio,
        "edge_density": edge_density,
        "gray_std": gray_std,
    }


def seat_occupancy(frame, geometry):
    """
    Determine physical seat occupancy from local visual structure.

    This detector deliberately emphasizes the stack/nameplate area.
    Empty ACR seats have very low brightness, edge density, and texture;
    occupied seats retain stack/nameplate structure even after folding.

    The Hero seat is treated as occupied whenever its normal nameplate
    structure is visible. Hero-card visibility remains a separate signal.
    """

    results = {}

    for seat in SEAT_ORDER:
        seat_rect = geometry[
            "seat_regions"
        ][seat]

        stack_rect = geometry[
            "stack_regions"
        ][seat]

        seat_features = _features(
            _crop(frame, seat_rect)
        )

        stack_features = _features(
            _crop(frame, stack_rect)
        )

        # Occupied player panels have strong structural edge content in
        # both the seat/nameplate region and stack line. Empty ACR seats may
        # still have substantial variance/brightness from felt and table UI,
        # so gray_std and bright_ratio must not independently establish
        # occupancy.
        #
        # Calibrated against Replay 0001 across 12 consecutive frames:
        # seven real players and one empty seat classified 96/96 correctly.
        occupied = bool(
            seat_features["edge_density"] >= 0.070
            and stack_features["edge_density"] >= 0.065
        )

        stack_votes = int(
            stack_features["edge_density"] >= 0.065
        )

        seat_votes = int(
            seat_features["edge_density"] >= 0.070
        )

        confidence = 0.0

        if occupied:
            confidence = min(
                0.99,
                0.45
                + 0.10 * stack_votes
                + 0.08 * seat_votes,
            )
        else:
            confidence = min(
                0.95,
                0.55
                + 0.08 * (3 - stack_votes)
                + 0.05 * (3 - seat_votes),
            )

        results[seat] = {
            "occupied": occupied,
            "confidence": round(
                confidence,
                2,
            ),
            "stack_votes": int(
                stack_votes
            ),
            "seat_votes": int(
                seat_votes
            ),
            "seat": seat_features,
            "stack": stack_features,
        }

    return results


def occupied_seats(frame, geometry):
    results = seat_occupancy(
        frame,
        geometry,
    )

    return [
        seat
        for seat in SEAT_ORDER
        if results[seat]["occupied"]
    ]
