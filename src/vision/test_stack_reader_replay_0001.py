import cv2
import json
from pathlib import Path

from src.vision.stack_reader import read_stack


ROOT = Path(__file__).resolve().parents[2]
SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260812_104222"
)

GEOM = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


def read_frame(index):
    path = SESSION / f"{index:04d}_full.png"

    if not path.exists():
        raise AssertionError(
            f"Replay 0001 frame missing: {path}"
        )

    image = cv2.imread(str(path))
    assert image is not None

    image = cv2.resize(
        image,
        (934, 696),
    )

    r = GEOM["stack_regions"]["seat_mid_left"]

    x = int(r["x"])
    y = int(r["y"])
    w = int(r["width"])
    h = int(r["height"])

    return read_stack(
        image[y:y+h, x:x+w]
    )


def main():
    # Before the BB 3-bet.
    baseline = read_frame(49)

    assert baseline["stack_bb"] == 65.6, baseline

    # Immediately after BB commits nine additional BB.
    after_three_bet = read_frame(51)

    assert after_three_bet["stack_bb"] == 56.6, (
        after_three_bet
    )

    # Later frame confirms the same stack.
    settled = read_frame(60)

    assert settled["stack_bb"] == 56.6, settled

    # Subsequent action changes the stack again.
    later = read_frame(63)

    assert later["stack_bb"] == 51.6, later

    print(
        "PASS Replay 0001 stack OCR: "
        "65.6 -> 56.6 -> 51.6"
    )


if __name__ == "__main__":
    main()
