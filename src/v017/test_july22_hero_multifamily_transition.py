from pathlib import Path
import cv2
import json

from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)

from src.v017.stack_continuity import (
    select_continuity_candidate,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOM = json.loads(
    Path("config/geometry.json").read_text()
)

SEAT = "hero"
REGION = GEOM["stack_regions"][SEAT]


def crop(number):
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

    x = int(REGION["x"])
    y = int(REGION["y"])
    w = int(REGION["width"])
    h = int(REGION["height"])

    return img[y:y+h, x:x+w]


def main():
    previous = 10.28

    for number in (101, 102):
        stack_crop = crop(number)

        normal = read_stack(
            stack_crop
        )

        independent = (
            read_stack_independent_consensus(
                stack_crop
            )
        )

        print()
        print(
            f"===== FRAME {number:04d} ====="
        )

        print(
            "normal =",
            normal,
        )

        print(
            "independent =",
            independent,
        )

        selected = select_continuity_candidate(
            previous,
            normal,
            independent,
            max_drop_bb=10.28,
        )

        print(
            "selected =",
            selected,
        )

        assert selected is not None

        assert 69.0 in selected["candidates"], (
            "expected independent missing-decimal candidate"
        )

        assert 6.9 in selected["candidates"], (
            "expected normal-reader 6.9 candidate"
        )

        assert selected["value"] == 6.9
        assert selected["delta_bb"] == 3.38

    print()
    print(
        "PASS: multi-family continuity selects observed "
        "6.9 over impossible 69.0 without decimal invention"
    )


if __name__ == "__main__":
    main()
