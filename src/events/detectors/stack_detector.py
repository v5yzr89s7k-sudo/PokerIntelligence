import cv2
import numpy as np
from src.events.utils import region_changed


def _crop(img, rect):
    x, y, w, h = map(int, [rect["x"], rect["y"], rect["width"], rect["height"]])
    return img[y:y+h, x:x+w]


def stack_region_diff(previous, current, rect):
    a = _crop(previous, rect)
    b = _crop(current, rect)

    if a.shape != b.shape or a.size == 0:
        return 0.0

    ag = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

    return float(np.mean(cv2.absdiff(ag, bg)))


DEFAULT_STACK_CHANGE_THRESHOLD = 8.0
HERO_STACK_CHANGE_THRESHOLD = 4.0


def stack_change_details(
    previous,
    current,
    geometry,
    threshold=DEFAULT_STACK_CHANGE_THRESHOLD,
):
    """
    Return raw visual stack-region movement.

    Hero uses a lower trigger because normal stack-text changes produce a
    smaller whole-region mean difference in the bottom-center stack ROI.
    This is only a candidate trigger. The coordinator still requires the
    region to settle, a trusted prior stack, confident OCR, and a positive
    quantitative chip delta before publishing STACK_CHANGED.
    """
    details = {}

    for seat, rect in geometry["stack_regions"].items():
        diff = stack_region_diff(previous, current, rect)

        seat_threshold = (
            HERO_STACK_CHANGE_THRESHOLD
            if seat == "hero"
            else threshold
        )

        details[seat] = {
            "mean_diff": diff,
            "threshold": seat_threshold,
            "changed": diff > seat_threshold,
        }

    return details


def stack_changed(previous, current, geometry):
    """
    Returns a list of seats whose stack region changed.
    """

    changed = []

    details = stack_change_details(previous, current, geometry)

    for seat, info in details.items():
        if info["changed"]:
            changed.append(seat)

    return changed
