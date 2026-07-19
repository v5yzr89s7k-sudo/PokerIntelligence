from collections import deque

import cv2
import numpy as np


def _hero_nameplate_rect(geometry):
    rect = (geometry.get("stack_regions") or {}).get("hero")
    if rect:
        return rect

    return (geometry.get("seat_regions") or {}).get("hero")


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


def _gray_hero_crop(frame, geometry):
    rect = _hero_nameplate_rect(geometry)
    if not rect or frame is None:
        return None

    crop = _crop(frame, rect)
    if crop.size == 0:
        return None

    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def hero_nameplate_diff(previous, current, geometry):
    a = _gray_hero_crop(previous, geometry)
    b = _gray_hero_crop(current, geometry)

    if a is None or b is None or a.shape != b.shape:
        return 0.0

    return float(np.mean(cv2.absdiff(a, b)))


def hero_nameplate_blinking(previous, current, geometry, threshold=5.0):
    return hero_nameplate_diff(previous, current, geometry) >= threshold


class HeroBlinkBuffer:
    """
    Non-blocking temporal Hero nameplate detector.

    The coordinator feeds one already-captured frame per loop. The detector
    stores only the cropped grayscale Hero nameplate region.
    """

    def __init__(
        self,
        max_samples=6,
        diff_threshold=5.0,
        mean_range_threshold=5.0,
        required_transitions=2,
    ):
        self.frames = deque(maxlen=int(max_samples))
        self.diff_threshold = float(diff_threshold)
        self.mean_range_threshold = float(mean_range_threshold)
        self.required_transitions = int(required_transitions)

        self.detected = False
        self.max_diff = 0.0
        self.mean_range = 0.0
        self.diffs = []

    def reset(self):
        self.frames.clear()
        self.detected = False
        self.max_diff = 0.0
        self.mean_range = 0.0
        self.diffs = []

    def update(self, frame, geometry):
        crop = _gray_hero_crop(frame, geometry)
        if crop is None:
            self.reset()
            return False

        self.frames.append(crop)

        if len(self.frames) < 3:
            self.detected = False
            return False

        frames = list(self.frames)

        self.diffs = [
            float(np.mean(cv2.absdiff(frames[i - 1], frames[i])))
            for i in range(1, len(frames))
        ]

        means = [float(np.mean(item)) for item in frames]

        self.max_diff = max(self.diffs) if self.diffs else 0.0
        self.mean_range = max(means) - min(means) if means else 0.0

        transition_count = sum(
            value >= self.diff_threshold
            for value in self.diffs
        )

        self.detected = (
            transition_count >= self.required_transitions
            or self.mean_range >= self.mean_range_threshold
        )

        return self.detected

    def summary(self):
        return {
            "blink_detected": self.detected,
            "max_diff": round(self.max_diff, 3),
            "mean_range": round(self.mean_range, 3),
            "diffs": [round(value, 3) for value in self.diffs],
            "sample_count": len(self.frames),
        }
