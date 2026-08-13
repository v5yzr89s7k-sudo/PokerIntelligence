from pathlib import Path
import json

import cv2

from src.vision.stack_reader import (
    read_stack_independent_consensus,
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


def read_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    assert path.exists(), path

    image = cv2.imread(str(path))
    assert image is not None

    image = cv2.resize(
        image,
        (934, 696),
    )

    region = GEOM["stack_regions"][SEAT]

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    return read_stack_independent_consensus(
        image[
            y:y + h,
            x:x + w,
        ]
    )


def main():
    before = read_frame(12)
    after = read_frame(13)

    print("===== FRAME 12 =====")
    print(before)

    print()
    print("===== FRAME 13 =====")
    print(after)

    assert before["stack_bb"] == 55.41
    assert before["votes"] == 5
    assert before["confidence"] >= 0.95
    assert (
        before["mode"]
        == "independent_segmentation"
    )

    assert after["stack_bb"] == 53.41
    assert after["votes"] == 5
    assert after["confidence"] >= 0.95

    print()
    print(
        "PASS public independent stack consensus: "
        "real Replay 0002 frame 12 resolves 55.41 and "
        "frame 13 resolves 53.41 through the production "
        "perception interface"
    )


if __name__ == "__main__":
    main()
