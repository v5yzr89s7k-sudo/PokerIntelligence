from pathlib import Path
import cv2
import json

from src.vision.stack_reader import (
    read_stack_independent_consensus,
)

from src.v017.stack_continuity import (
    select_stable_transition,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOM = json.loads(
    Path("config/geometry.json").read_text()
)

SEAT = "seat_lower_left"


def read(number):
    img = cv2.imread(
        str(ROOT / f"{number:04d}_full.png")
    )

    if img is None:
        raise RuntimeError(number)

    if img.shape[:2] != (696, 934):
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    r = GEOM["stack_regions"][SEAT]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return read_stack_independent_consensus(
        img[y:y+h, x:x+w]
    )


def main():
    # BB started at 48.57 and posted 1 BB.
    #
    # HandEngine owns that poker fact. Therefore the authoritative
    # stack baseline entering the flop is 47.57.
    previous_stack = 47.57

    readings = [
        (
            number,
            read(number),
        )
        for number in range(84, 94)
    ]

    transition = select_stable_transition(
        readings,
        previous_value=previous_stack,
        max_drop_bb=10.0,
        min_support=3,
        min_consecutive=2,
    )

    print(
        "transition =",
        transition,
    )

    assert transition is not None
    assert transition["frame"] == 90
    assert transition["value"] == 44.2
    assert transition["delta_bb"] == 3.37
    assert transition["frames"] == [
        90,
        91,
    ]

    print()
    print(
        "PASS: BB pixel stack transition "
        "47.57 -> 44.20 = 3.37 BB"
    )


if __name__ == "__main__":
    main()
