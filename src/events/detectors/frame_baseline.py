import cv2
import numpy as np


class FrameBaseline:
    """
    Stores baseline ROI images and measures visual change against them.

    This class does not decide whether a region contains a bet. It only
    provides generic change features for downstream perception logic.
    """

    def __init__(
        self,
        pixel_threshold=18,
        blur_size=3,
    ):
        self.pixel_threshold = int(pixel_threshold)
        self.blur_size = int(blur_size)
        self._regions = {}

    def reset(self):
        self._regions.clear()

    @staticmethod
    def _crop(frame, rect):
        x = int(rect["x"])
        y = int(rect["y"])
        width = int(rect["width"])
        height = int(rect["height"])

        return frame[
            y:y + height,
            x:x + width,
        ]

    def _prepare(self, image):
        if image.size == 0:
            return image

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self.blur_size > 1:
            size = self.blur_size

            if size % 2 == 0:
                size += 1

            gray = cv2.GaussianBlur(
                gray,
                (size, size),
                0,
            )

        return gray

    def capture(self, key, frame, rect):
        crop = self._crop(frame, rect)

        if crop.size == 0:
            self._regions.pop(key, None)
            return False

        self._regions[key] = self._prepare(crop).copy()
        return True

    def has_baseline(self, key):
        return key in self._regions

    def difference(self, key, frame, rect):
        crop = self._crop(frame, rect)

        empty = {
            "baseline_ready": False,
            "difference_ratio": 0.0,
            "mean_difference": 0.0,
            "changed_pixels": 0,
            "changed_bbox_x": 0,
            "changed_bbox_y": 0,
            "changed_bbox_width": 0,
            "changed_bbox_height": 0,
            "changed_bbox_area": 0,
            "changed_contour_count": 0,
            "largest_changed_contour_area": 0.0,
        }

        if crop.size == 0:
            return empty

        current = self._prepare(crop)
        baseline = self._regions.get(key)

        if baseline is None:
            return empty

        if baseline.shape != current.shape:
            self._regions[key] = current.copy()
            return empty

        difference = cv2.absdiff(
            baseline,
            current,
        )

        mean_difference = float(np.mean(difference))

        changed_mask = (
            difference >= self.pixel_threshold
        ).astype(np.uint8) * 255

        kernel = np.ones((3, 3), dtype=np.uint8)

        changed_mask = cv2.morphologyEx(
            changed_mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1,
        )

        changed_mask = cv2.morphologyEx(
            changed_mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=1,
        )

        changed_pixels = int(
            cv2.countNonZero(changed_mask)
        )

        total_pixels = int(
            changed_mask.shape[0]
            * changed_mask.shape[1]
        )

        difference_ratio = (
            float(changed_pixels / total_pixels)
            if total_pixels
            else 0.0
        )

        points = cv2.findNonZero(changed_mask)

        if points is None:
            bbox_x = 0
            bbox_y = 0
            bbox_width = 0
            bbox_height = 0
        else:
            (
                bbox_x,
                bbox_y,
                bbox_width,
                bbox_height,
            ) = cv2.boundingRect(points)

        contours, _ = cv2.findContours(
            changed_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        contour_areas = [
            float(cv2.contourArea(contour))
            for contour in contours
        ]

        return {
            "baseline_ready": True,
            "difference_ratio": difference_ratio,
            "mean_difference": mean_difference,
            "changed_pixels": changed_pixels,
            "changed_bbox_x": int(bbox_x),
            "changed_bbox_y": int(bbox_y),
            "changed_bbox_width": int(bbox_width),
            "changed_bbox_height": int(bbox_height),
            "changed_bbox_area": int(
                bbox_width * bbox_height
            ),
            "changed_contour_count": len(contours),
            "largest_changed_contour_area": max(
                contour_areas,
                default=0.0,
            ),
        }
