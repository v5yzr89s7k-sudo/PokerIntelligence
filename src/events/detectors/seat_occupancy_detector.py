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

        # Stack/name text is the most stable occupancy evidence. Requiring
        # agreement from more than one visual property avoids classifying
        # plain felt or a single transient pixel group as an occupied seat.
        stack_votes = sum([
            stack_features["gray_std"] >= 14.0,
            stack_features["edge_density"] >= 0.043,
            stack_features["bright_ratio"] >= 0.010,
        ])

        seat_votes = sum([
            seat_features["gray_std"] >= 20.0,
            seat_features["edge_density"] >= 0.040,
            seat_features["bright_ratio"] >= 0.020,
        ])

        occupied = bool(
            stack_votes >= 2
            or (
                stack_votes >= 1
                and seat_votes >= 2
            )
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
