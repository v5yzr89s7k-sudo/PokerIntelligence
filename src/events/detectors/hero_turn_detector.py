import time
import cv2
import numpy as np


def _hero_nameplate_rect(geometry):
    # Prefer stack/nameplate region because ACR blink affects the hero nameplate area.
    rect = (geometry.get("stack_regions") or {}).get("hero")
    if rect:
        return rect

    # Fallback: derive from hero seat region if stack_regions is missing.
    rect = (geometry.get("seat_regions") or {}).get("hero")
    if rect:
        return rect

    return None


def _crop(img, rect):
    x, y, w, h = map(int, [rect["x"], rect["y"], rect["width"], rect["height"]])
    return img[y:y+h, x:x+w]


def hero_nameplate_diff(previous, current, geometry):
    rect = _hero_nameplate_rect(geometry)
    if not rect:
        return 0.0

    a = _crop(previous, rect)
    b = _crop(current, rect)

    if a.shape != b.shape or a.size == 0:
        return 0.0

    ag = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

    return float(np.mean(cv2.absdiff(ag, bg)))


def hero_nameplate_blinking(previous, current, geometry, threshold=5.0):
    return hero_nameplate_diff(previous, current, geometry) >= threshold


def hero_nameplate_blinking_rolling(capture_fn, latest_capture_fn, geometry, samples=6, delay=0.18, threshold=5.0):
    """
    Samples multiple frames over roughly one second.

    Returns:
      (blink_detected: bool, max_diff: float, diffs: list[float])
    """
    frames = []

    for _ in range(samples):
        capture_fn()
        path = latest_capture_fn()
        if not path:
            time.sleep(delay)
            continue

        img = cv2.imread(str(path))
        if img is None:
            time.sleep(delay)
            continue

        img = cv2.resize(img, (934, 696))
        frames.append(img)
        time.sleep(delay)

    diffs = []
    for i in range(1, len(frames)):
        diffs.append(hero_nameplate_diff(frames[i - 1], frames[i], geometry))

    max_diff = max(diffs) if diffs else 0.0
    return max_diff >= threshold, max_diff, diffs
