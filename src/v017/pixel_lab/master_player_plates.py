"""
V0.17 authentic ACR master player-plate primitives.

GENERATOR SIDE ONLY.

Each physical seat gets its own clean plate derived from the immutable
authentic ACR master at that seat's exact native geometry.

No plate is stretched from another seat.

The clean primitive removes visible player-name and stack glyphs while
preserving the authentic ACR plate/card/background pixels.

This module supplies physical pixels only. It never supplies semantic
truth to production.
"""

from pathlib import Path

import cv2
import numpy as np

from src.v017.pixel_lab.master_frame import (
    SEATS,
    load_master_copy,
)


ROOT = Path(__file__).resolve().parents[3]

OUT = (
    ROOT
    / "runtime/pixel_lab/master/"
      "player_plates"
)


def plate_bounds(
    geometry,
    seat,
):
    seat_rect = geometry[
        "seat_regions"
    ][seat]

    stack_rect = geometry[
        "stack_regions"
    ][seat]

    x1 = min(
        int(seat_rect["x"]),
        int(stack_rect["x"]),
    )

    y1 = min(
        int(seat_rect["y"]),
        int(stack_rect["y"]),
    )

    x2 = max(
        int(
            seat_rect["x"]
            + seat_rect["width"]
        ),
        int(
            stack_rect["x"]
            + stack_rect["width"]
        ),
    )

    y2 = max(
        int(
            seat_rect["y"]
            + seat_rect["height"]
        ),
        int(
            stack_rect["y"]
            + stack_rect["height"]
        ),
    )

    return (
        x1,
        y1,
        x2,
        y2,
    )


def _text_mask(
    plate,
):
    gray = cv2.cvtColor(
        plate,
        cv2.COLOR_BGR2GRAY,
    )

    hsv = cv2.cvtColor(
        plate,
        cv2.COLOR_BGR2HSV,
    )

    # Opponent names: cream / near-white.
    cream = (
        (gray >= 135)
        & (hsv[:, :, 1] <= 150)
    )

    # Stack values: saturated ACR green.
    green = (
        (hsv[:, :, 0] >= 35)
        & (hsv[:, :, 0] <= 100)
        & (hsv[:, :, 1] >= 70)
        & (hsv[:, :, 2] >= 100)
    )

    mask = (
        cream | green
    ).astype(np.uint8) * 255

    # Cover antialiasing around glyphs.
    return cv2.dilate(
        mask,
        np.ones(
            (9, 9),
            dtype=np.uint8,
        ),
        iterations=1,
    )


def clean_plate(
    plate,
):
    """
    Remove name/stack glyph pixels using authentic neighboring pixels
    from the same physical row.

    This is the generalized version of the already visually accepted
    upper-left clean-plate proof.
    """
    original = plate.copy()
    clean = plate.copy()

    mask = _text_mask(
        original
    )

    for yy in range(
        clean.shape[0]
    ):
        row_mask = (
            mask[yy] > 0
        )

        if not row_mask.any():
            continue

        xs = np.flatnonzero(
            row_mask
        )

        starts = [
            int(xs[0])
        ]
        ends = []

        for left, right in zip(
            xs[:-1],
            xs[1:],
        ):
            if right != left + 1:
                ends.append(
                    int(left)
                )
                starts.append(
                    int(right)
                )

        ends.append(
            int(xs[-1])
        )

        for start, end in zip(
            starts,
            ends,
        ):
            donor_left = max(
                0,
                start - 30,
            )

            donor_right = min(
                clean.shape[1],
                end + 31,
            )

            donors = []

            if donor_left < start:
                donors.append(
                    original[
                        yy,
                        donor_left:start,
                    ]
                )

            if end + 1 < donor_right:
                donors.append(
                    original[
                        yy,
                        end + 1:
                        donor_right,
                    ]
                )

            if not donors:
                continue

            pixels = np.concatenate(
                donors,
                axis=0,
            )

            donor_gray = cv2.cvtColor(
                pixels.reshape(
                    -1,
                    1,
                    3,
                ),
                cv2.COLOR_BGR2GRAY,
            ).reshape(-1)

            # Keep dark authentic plate/background pixels only.
            pixels = pixels[
                (donor_gray >= 15)
                & (donor_gray <= 125)
            ]

            if len(pixels) == 0:
                continue

            fill = np.median(
                pixels,
                axis=0,
            ).astype(np.uint8)

            clean[
                yy,
                start:end + 1,
            ] = fill

    return (
        clean,
        mask,
    )


def build_clean_player_plates(
    geometry,
):
    """
    Derive all eight exact-native clean player plates from a fresh
    immutable-master copy.
    """
    image = load_master_copy()

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = {}

    for seat in SEATS:
        x1, y1, x2, y2 = (
            plate_bounds(
                geometry,
                seat,
            )
        )

        original = image[
            y1:y2,
            x1:x2,
        ].copy()

        clean, mask = (
            clean_plate(
                original
            )
        )

        clean_path = (
            OUT
            / f"{seat}_clean.png"
        )

        original_path = (
            OUT
            / f"{seat}_original.png"
        )

        mask_path = (
            OUT
            / f"{seat}_mask.png"
        )

        assert cv2.imwrite(
            str(clean_path),
            clean,
        )

        assert cv2.imwrite(
            str(original_path),
            original,
        )

        assert cv2.imwrite(
            str(mask_path),
            mask,
        )

        results[seat] = {
            "bounds": {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
            },
            "shape": tuple(
                clean.shape
            ),
            "clean_path":
                clean_path,
            "original_path":
                original_path,
            "mask_path":
                mask_path,
        }

    return results
