from pathlib import Path

import cv2

from src.vision.stack_reader import read_stack
import json


SESSION = Path(
    "runtime/debug/action_sequence/20260808_114630"
)

GEOMETRY = json.loads(
    Path("config/geometry.json").read_text()
)

SEAT = "seat_mid_right"


def read_frame(idx):
    path = SESSION / f"{idx:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0002 frame missing: {path}"
        )

    image = cv2.imread(str(path))

    if image is None:
        raise AssertionError(
            f"Could not read: {path}"
        )

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOMETRY["stack_regions"][SEAT]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    result = read_stack(
        image[y:y+h, x:x+w]
    )

    return path, result


def main():
    # Human-verified Replay 0002 ground truth:
    #
    # UTG+1:
    #   55.41 BB before action
    #   raises to 2 BB
    #   53.41 BB after action
    #
    # The currently selected OCR result is known to confuse
    # the leading 5 with 9.

    before_path, before = read_frame(12)
    after_path, after = read_frame(13)

    print()
    print("===== FRAME 12 — BEFORE UTG+1 ACTION =====")
    print("path:", before_path)
    print(before)

    print()
    print("===== FRAME 13 — AFTER UTG+1 ACTION =====")
    print("path:", after_path)
    print(after)

    print()
    print("===== HUMAN-VERIFIED GROUND TRUTH =====")
    print("before : 55.41 BB")
    print("after  : 53.41 BB")
    print("delta  : 2.00 BB")
    print("action : raise to 2 BB")

    print()
    print("===== CURRENT READER =====")
    print("before :", before.get("stack_bb"))
    print("after  :", after.get("stack_bb"))

    if (
        before.get("stack_bb") == 55.41
        and after.get("stack_bb") == 53.41
    ):
        print()
        print(
            "PASS: Replay 0002 UTG+1 OCR now matches "
            "human-verified ground truth"
        )
        return

    print()
    print(
        "EXPECTED FAILURE: stack reader does not yet match "
        "human-verified Replay 0002 ground truth"
    )

    raise SystemExit(1)


if __name__ == "__main__":
    main()
