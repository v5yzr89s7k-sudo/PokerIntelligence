from pathlib import Path
import json

import cv2

from src.vision.stack_reader import (
    _prepare_images,
    _independent_segmentation_consensus,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260808_114630"
)

GEOM = json.loads(
    Path("config/geometry.json").read_text()
)

SEAT = "seat_mid_right"


def independent_read(idx):
    path = SESSION / f"{idx:04d}_full.png"

    if not path.exists():
        raise AssertionError(path)

    image = cv2.imread(str(path))

    if image is None:
        raise AssertionError(path)

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOM["stack_regions"][SEAT]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    crop = image[y:y+h, x:x+w]

    _, gray, _ = _prepare_images(crop)

    return _independent_segmentation_consensus(
        gray
    )


def main():
    before_frames = (10, 11, 12)
    after_frames = (
        13, 14, 15,
        20, 30, 40,
        50, 60, 70, 79,
    )

    print("===== BEFORE ACTION =====")

    for idx in before_frames:
        value, votes, readings = independent_read(idx)

        print(idx, value, votes)

        assert value == 55.41, (
            idx,
            value,
            votes,
            readings,
        )

        assert votes >= 3

    print()
    print("===== AFTER ACTION =====")

    for idx in after_frames:
        value, votes, readings = independent_read(idx)

        print(idx, value, votes)

        assert value == 53.41, (
            idx,
            value,
            votes,
            readings,
        )

        assert votes >= 3

    print()
    print(
        "PASS independent stack segmentation: "
        "multi-threshold PSM13 consensus independently recovers "
        "stable 55.41 -> 53.41 transition across real frames"
    )


if __name__ == "__main__":
    main()
