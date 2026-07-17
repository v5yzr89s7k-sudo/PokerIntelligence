import cv2
import numpy as np

from src.events.detectors.bet_region_detector import bet_region_signal


RECT = {
    "x": 0,
    "y": 0,
    "width": 90,
    "height": 45,
}


def test_empty_region_has_zero_features():
    frame = np.zeros((45, 90, 3), dtype=np.uint8)

    signal = bet_region_signal(frame, RECT)

    assert signal["occupied"] is False
    assert signal["foreground_area"] == 0
    assert signal["bbox_width"] == 0
    assert signal["bbox_height"] == 0
    assert signal["contour_count"] == 0


def test_visible_blob_produces_geometric_features():
    frame = np.zeros((45, 90, 3), dtype=np.uint8)

    cv2.rectangle(
        frame,
        (20, 10),
        (60, 32),
        (255, 255, 255),
        thickness=-1,
    )

    signal = bet_region_signal(frame, RECT)

    assert signal["occupied"] is True
    assert signal["foreground_area"] > 0
    assert signal["bbox_width"] > 0
    assert signal["bbox_height"] > 0
    assert signal["bbox_area"] > 0
    assert signal["horizontal_extent"] > 0
    assert signal["vertical_extent"] > 0
    assert signal["contour_count"] >= 1
    assert signal["largest_contour_area"] > 0


def test_larger_blob_has_larger_foreground_area():
    small = np.zeros((45, 90, 3), dtype=np.uint8)
    large = np.zeros((45, 90, 3), dtype=np.uint8)

    cv2.rectangle(
        small,
        (30, 15),
        (48, 28),
        (255, 255, 255),
        thickness=-1,
    )

    cv2.rectangle(
        large,
        (15, 7),
        (70, 36),
        (255, 255, 255),
        thickness=-1,
    )

    small_signal = bet_region_signal(small, RECT)
    large_signal = bet_region_signal(large, RECT)

    assert (
        large_signal["foreground_area"]
        > small_signal["foreground_area"]
    )
    assert (
        large_signal["bbox_area"]
        > small_signal["bbox_area"]
    )


if __name__ == "__main__":
    tests = [
        test_empty_region_has_zero_features,
        test_visible_blob_produces_geometric_features,
        test_larger_blob_has_larger_foreground_area,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print("ALL BET REGION FEATURE TESTS PASSED")
