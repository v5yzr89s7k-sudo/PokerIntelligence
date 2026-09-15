from pathlib import Path
import cv2
import json

from src.vision.stack_reader import (
    read_stack,
)
from src.v017.fast_stack_resolver import (
    resolve_fast_stack,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOMETRY = json.loads(
    Path(
        "config/geometry.json"
    ).read_text()
)

CASES = [
    (40,  "seat_lower_right", 58.55, 58.55, "BTN false wake"),
    (42,  "seat_lower_right", 58.55, 56.55, "BTN preflop"),
    (48,  "hero",             11.78, 10.28, "Hero preflop"),
    (90,  "seat_lower_left",  47.57, 44.20, "BB flop"),
    (101, "hero",             10.28,  6.90, "Hero flop"),
    (127, "seat_lower_left",  44.20, 37.45, "BB river"),
]


def load(number):
    frame = cv2.imread(
        str(
            ROOT
            / f"{number:04d}_full.png"
        )
    )

    if frame is None:
        raise RuntimeError(
            number
        )

    if frame.shape[:2] != (
        696,
        934,
    ):
        frame = cv2.resize(
            frame,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    return frame


def crop(frame, seat):
    r = (
        GEOMETRY[
            "stack_regions"
        ][seat]
    )

    return frame[
        int(r["y"]):
        int(r["y"] + r["height"]),
        int(r["x"]):
        int(r["x"] + r["width"]),
    ]


def main():
    for (
        number,
        seat,
        prior,
        expected,
        label,
    ) in CASES:
        reading = read_stack(
            crop(
                load(number),
                seat,
            )
        )

        result = resolve_fast_stack(
            reading,
            prior,
        )

        print(
            label,
            "frame=",
            number,
            "reader=",
            reading.get("stack_bb"),
            "resolved=",
            result.value,
            "support=",
            result.support,
            "candidates=",
            result.candidates,
        )

        assert result.resolved, (
            label,
            result,
        )

        assert abs(
            result.value
            - expected
        ) <= 0.02, (
            label,
            result,
            expected,
        )

    print(
        "V0.17 JULY22 FAST STACK RESOLVER: PASS"
    )


if __name__ == "__main__":
    main()
