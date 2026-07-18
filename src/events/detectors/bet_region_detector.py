import os
from pathlib import Path

import cv2
import numpy as np


def _crop(img, rect):
    x, y, w, h = map(
        int,
        [
            rect["x"],
            rect["y"],
            rect["width"],
            rect["height"],
        ],
    )
    return img[y:y + h, x:x + w]


def _empty_signal():
    return {
        "bright_ratio": 0.0,
        "edge_density": 0.0,
        "foreground_ratio": 0.0,
        "foreground_area": 0,
        "bbox_x": 0,
        "bbox_y": 0,
        "bbox_width": 0,
        "bbox_height": 0,
        "bbox_area": 0,
        "horizontal_extent": 0.0,
        "vertical_extent": 0.0,
        "contour_count": 0,
        "largest_contour_area": 0.0,
        "occupied": False,
    }


def bet_region_signal(frame, rect):
    crop = _crop(frame, rect)

    # Debug: save the exact ROI analyzed for Hero.
    if rect.get("_seat") == "hero" and crop.size:
        debug = Path("runtime/debug")
        debug.mkdir(parents=True, exist_ok=True)

        baseline_path = debug / "hero_bet_roi_baseline.png"

        # Save the first observed Hero bet ROI for reference.
        if not baseline_path.exists():
            cv2.imwrite(str(baseline_path), crop)

    if crop.size == 0:
        return _empty_signal()

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    bright_mask = (gray > 150).astype(np.uint8) * 255
    bright_ratio = float((bright_mask > 0).mean())

    edges = cv2.Canny(gray, 80, 160)
    edge_density = float((edges > 0).mean())

    # Combine bright chip/text pixels with edges. Morphological closing joins
    # nearby fragments while keeping this detector inexpensive.
    foreground = cv2.bitwise_or(bright_mask, edges)

    kernel = np.ones((3, 3), dtype=np.uint8)
    foreground = cv2.morphologyEx(
        foreground,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=1,
    )

    foreground_area = int(cv2.countNonZero(foreground))
    total_area = int(foreground.shape[0] * foreground.shape[1])
    foreground_ratio = (
        float(foreground_area / total_area)
        if total_area
        else 0.0
    )

    points = cv2.findNonZero(foreground)

    if points is None:
        bbox_x = 0
        bbox_y = 0
        bbox_width = 0
        bbox_height = 0
    else:
        bbox_x, bbox_y, bbox_width, bbox_height = cv2.boundingRect(points)

    bbox_area = int(bbox_width * bbox_height)

    crop_height, crop_width = gray.shape[:2]

    horizontal_extent = (
        float(bbox_width / crop_width)
        if crop_width
        else 0.0
    )
    vertical_extent = (
        float(bbox_height / crop_height)
        if crop_height
        else 0.0
    )

    contours, _ = cv2.findContours(
        foreground,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    contour_areas = [
        float(cv2.contourArea(contour))
        for contour in contours
    ]

    contour_count = len(contours)
    largest_contour_area = max(contour_areas, default=0.0)

    legacy_occupied = (
        bright_ratio > 0.035
        or edge_density > 0.055
    )

    return {
        "bright_ratio": bright_ratio,
        "edge_density": edge_density,
        "foreground_ratio": foreground_ratio,
        "foreground_area": foreground_area,
        "bbox_x": int(bbox_x),
        "bbox_y": int(bbox_y),
        "bbox_width": int(bbox_width),
        "bbox_height": int(bbox_height),
        "bbox_area": bbox_area,
        "horizontal_extent": horizontal_extent,
        "vertical_extent": vertical_extent,
        "contour_count": contour_count,
        "largest_contour_area": largest_contour_area,

        # This value is replaced with baseline-aware occupancy when a
        # baseline is available. Retain the original decision for telemetry.
        "legacy_occupied": legacy_occupied,
        "occupied": legacy_occupied,
    }


def bet_region_occupancy(
    frame,
    geometry,
    baseline=None,
):
    result = {}

    for seat, rect in geometry.get(
        "bet_regions",
        {},
    ).items():
        region = dict(rect)
        region["_seat"] = seat

        signal = bet_region_signal(
            frame,
            region,
        )

        if baseline is not None:
            baseline_features = baseline.difference(
                f"bet_region:{seat}",
                frame,
                rect,
            )
            signal.update(baseline_features)


        baseline_ready = bool(
            signal.get("baseline_ready", False)
        )

        difference_ratio = float(
            signal.get("difference_ratio", 0.0)
            or 0.0
        )
        changed_pixels = int(
            signal.get("changed_pixels", 0)
            or 0
        )
        largest_changed = float(
            signal.get(
                "largest_changed_contour_area",
                0.0,
            )
            or 0.0
        )

        visual_present = bool(
            signal.get("bright_ratio", 0.0) > 0.030
            or signal.get("edge_density", 0.0) > 0.050
            or signal.get("foreground_ratio", 0.0) > 0.080
        )

        baseline_changed = bool(
            difference_ratio >= 0.080
            and changed_pixels >= 250
            and largest_changed >= 100.0
        )

        if baseline_ready:
            signal["occupied"] = bool(
                signal.get("legacy_occupied", False)
                or (
                    baseline_changed
                    and visual_present
                )
            )

        signal["baseline_changed"] = baseline_changed
        signal["visual_present"] = visual_present

        if seat == "hero" and baseline_changed:
            debug = Path("runtime/debug")
            debug.mkdir(parents=True, exist_ok=True)

            changed_path = debug / "hero_bet_roi_changed.png"

            if not changed_path.exists():
                hero_crop = _crop(frame, rect)

                if hero_crop.size:
                    cv2.imwrite(
                        str(changed_path),
                        hero_crop,
                    )

        signal["occupancy_rule"] = (
            "baseline_evidence"
            if baseline_ready
            else "legacy_fallback"
        )

        if (
            seat == "hero"
            and os.environ.get(
                "BET_SIGNAL_DEBUG",
                "",
            ).strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            print(
                "[HERO_BET_SIGNAL]",
                f"bright={signal.get('bright_ratio', 0.0):.4f}",
                f"edge={signal.get('edge_density', 0.0):.4f}",
                f"foreground={signal.get('foreground_ratio', 0.0):.4f}",
                f"bbox_area={signal.get('bbox_area', 0)}",
                f"h_extent={signal.get('horizontal_extent', 0.0):.3f}",
                f"v_extent={signal.get('vertical_extent', 0.0):.3f}",
                f"contours={signal.get('contour_count', 0)}",
                f"largest={signal.get('largest_contour_area', 0.0):.1f}",
                f"baseline={signal.get('baseline_ready', False)}",
                f"diff={signal.get('difference_ratio', 0.0):.4f}",
                f"mean_diff={signal.get('mean_difference', 0.0):.2f}",
                f"changed_pixels={signal.get('changed_pixels', 0)}",
                f"changed_bbox={signal.get('changed_bbox_area', 0)}",
                f"changed_contours={signal.get('changed_contour_count', 0)}",
                f"changed_largest={signal.get('largest_changed_contour_area', 0.0):.1f}",
                f"baseline_changed={signal.get('baseline_changed', False)}",
                f"visual_present={signal.get('visual_present', False)}",
                f"legacy={signal.get('legacy_occupied', False)}",
                f"occupied={signal.get('occupied', False)}",
                flush=True,
            )

        result[seat] = signal

    return result


def occupied_bet_regions(frame, geometry):
    details = bet_region_occupancy(frame, geometry)

    return [
        seat
        for seat, info in details.items()
        if info.get("occupied")
    ]
