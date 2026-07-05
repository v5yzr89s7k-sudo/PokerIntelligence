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


def stack_change_details(previous, current, geometry, threshold=8.0):
    details = {}

    for seat, rect in geometry["stack_regions"].items():
        diff = stack_region_diff(previous, current, rect)
        details[seat] = {
            "mean_diff": diff,
            "changed": diff > threshold,
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
