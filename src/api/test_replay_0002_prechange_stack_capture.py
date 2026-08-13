from pathlib import Path
import json

import cv2

from src.events.local_event_detector import LocalEventDetector
from src.vision.stack_reader import (
    read_stack,
    _independent_segmentation_consensus,
    _prepare_images,
)


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260808_114630"
)

GEOM = json.loads(
    (ROOT / "config/geometry.json").read_text()
)

SEAT = "seat_mid_right"


def load_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    assert path.exists(), path

    image = cv2.imread(str(path))
    assert image is not None

    return cv2.resize(
        image,
        (934, 696),
    )


def crop_stack(image):
    region = GEOM["stack_regions"][SEAT]

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    return image[
        y:y+h,
        x:x+w,
    ]


def independent_read(image):
    crop = crop_stack(image)

    _, gray, _ = _prepare_images(crop)

    return _independent_segmentation_consensus(
        gray
    )


def main():
    before = load_frame(12)
    after = load_frame(13)

    detector = LocalEventDetector()

    # Reproduce the production lifecycle exactly:
    # detector.previous_frame is the preceding frame when detect()
    # evaluates the current frame.
    detector.previous_frame = before.copy()

    preserved_previous = detector.previous_frame.copy()

    changes = detector.detect(after)

    detail = (
        changes.stack_change_details.get(SEAT)
        or {}
    )

    print("===== RAW 12 -> 13 DETECTOR =====")
    print(detail)

    print()
    print(
        "stack_changed_seats:",
        changes.stack_changed_seats,
    )

    # The key contract:
    # if raw stack motion fires, the coordinator had access to the
    # immediately preceding image before detect() advanced its baseline.
    assert detail, changes.stack_change_details

    if detail.get("changed"):
        assert SEAT in changes.stack_changed_seats

    # Verify detect() advanced its internal baseline after comparison.
    assert detector.previous_frame is after

    # But our preserved reference/copy is still the true pre-change image.
    provisional = read_stack(
        crop_stack(preserved_previous)
    )

    independent_value, independent_votes, independent_raw = (
        independent_read(preserved_previous)
    )

    print()
    print("===== PRESERVED PRE-CHANGE OCR =====")
    print("provisional:", provisional)
    print(
        "independent:",
        independent_value,
        "votes=",
        independent_votes,
    )

    for item in independent_raw:
        print(
            " ",
            item.get("variant"),
            repr(item.get("raw")),
            item.get("stack_bb"),
        )

    assert independent_value == 55.41, (
        independent_value,
        independent_votes,
        independent_raw,
    )

    assert independent_votes >= 3

    # Confirm the next image is independently 53.41.
    after_value, after_votes, after_raw = (
        independent_read(after)
    )

    print()
    print("===== CURRENT FRAME OCR =====")
    print(
        "independent:",
        after_value,
        "votes=",
        after_votes,
    )

    assert after_value == 53.41, (
        after_value,
        after_votes,
        after_raw,
    )

    assert after_votes >= 3

    print()
    print(
        "PASS Replay 0002 pre-change capture: "
        "production detector comparison preserves access to "
        "the real 55.41 pre-action pixels before advancing "
        "to the 53.41 current frame"
    )


if __name__ == "__main__":
    main()
