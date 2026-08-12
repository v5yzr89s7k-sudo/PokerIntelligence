import cv2
import json
from pathlib import Path

from src.vision.stack_reader import read_stack


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260808_114630"
)

GEOM = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


def read_frame(seat, index):
    path = SESSION / f"{index:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0002 frame missing: {path}"
        )

    image = cv2.imread(str(path))
    assert image is not None

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOM["stack_regions"][seat]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return read_stack(
        image[y:y+h, x:x+w]
    )


def main():
    # --------------------------------------------------------
    # UTG+1 open
    # --------------------------------------------------------

    utg1_before = read_frame(
        "seat_mid_right",
        12,
    )

    utg1_after = read_frame(
        "seat_mid_right",
        15,
    )

    assert utg1_before["stack_bb"] == 99.41, (
        utg1_before
    )

    assert utg1_after["stack_bb"] == 93.41, (
        utg1_after
    )

    assert round(
        utg1_before["stack_bb"]
        - utg1_after["stack_bb"],
        2,
    ) == 6.0

    # --------------------------------------------------------
    # LJ 3-bet
    # --------------------------------------------------------

    lj_before = read_frame(
        "seat_lower_right",
        26,
    )

    lj_after = read_frame(
        "seat_lower_right",
        29,
    )

    assert lj_before["stack_bb"] == 72.08, (
        lj_before
    )

    assert lj_after["stack_bb"] == 65.08, (
        lj_after
    )

    assert round(
        lj_before["stack_bb"]
        - lj_after["stack_bb"],
        2,
    ) == 7.0

    # --------------------------------------------------------
    # Hero HJ call
    # --------------------------------------------------------

    hero_before = read_frame(
        "hero",
        34,
    )

    hero_after = read_frame(
        "hero",
        37,
    )

    assert hero_before["stack_bb"] == 32.42, (
        hero_before
    )

    assert hero_after["stack_bb"] == 25.42, (
        hero_after
    )

    assert round(
        hero_before["stack_bb"]
        - hero_after["stack_bb"],
        2,
    ) == 7.0

    print(
        "PASS Replay 0002 stack OCR: "
        "UTG+1 99.41->93.41 (6 BB), "
        "LJ 72.08->65.08 (7 BB), "
        "Hero 32.42->25.42 (7 BB)"
    )


if __name__ == "__main__":
    main()
