from pathlib import Path
import cv2
import json

from src.v017.stack_motion_gate import (
    measure_stack_motion,
)


ROOT = Path(
    "runtime/debug/action_sequence/20260722_152155"
)

GEOMETRY = json.loads(
    Path(
        "config/geometry.json"
    ).read_text()
)


def load(number):
    frame = cv2.imread(
        str(
            ROOT
            / f"{number:04d}_full.png"
        )
    )

    if frame is None:
        raise RuntimeError(
            f"missing frame {number}"
        )

    if frame.shape[:2] != (
        696,
        934,
    ):
        frame = cv2.resize(
            frame,
            (
                934,
                696,
            ),
            interpolation=cv2.INTER_AREA,
        )

    return frame


def motion(number, seat):
    return measure_stack_motion(
        load(number - 1),
        load(number),
        GEOMETRY,
        seat,
    )


def main():
    # Earliest known physical quantitative transitions.
    expected_wakes = [
        (
            42,
            "seat_lower_right",
            "BTN preflop",
        ),
        (
            48,
            "hero",
            "Hero preflop",
        ),
        (
            90,
            "seat_lower_left",
            "BB flop",
        ),
        (
            101,
            "hero",
            "Hero flop",
        ),
        (
            127,
            "seat_lower_left",
            "BB river",
        ),
    ]

    print(
        "===== EXPECTED QUANTITATIVE WAKES ====="
    )

    for number, seat, label in (
        expected_wakes
    ):
        result = motion(
            number,
            seat,
        )

        print(
            f"{number:04d}",
            f"{seat:20s}",
            label,
            f"fraction={result.changed_fraction:.4f}",
            f"mean={result.mean_diff:.2f}",
            f"wake={result.wake}",
        )

        assert result.wake, (
            label,
            result,
        )

    # Representative quiet frames immediately after settled
    # transitions must not repeatedly wake OCR.
    quiet = [
        (
            43,
            "seat_lower_right",
        ),
        (
            49,
            "hero",
        ),
        (
            91,
            "seat_lower_left",
        ),
        (
            102,
            "hero",
        ),
        (
            128,
            "seat_lower_left",
        ),
    ]

    print()
    print(
        "===== SETTLED QUIET FRAMES ====="
    )

    for number, seat in quiet:
        result = motion(
            number,
            seat,
        )

        print(
            f"{number:04d}",
            f"{seat:20s}",
            f"fraction={result.changed_fraction:.4f}",
            f"mean={result.mean_diff:.2f}",
            f"wake={result.wake}",
        )

        assert not result.wake, (
            number,
            seat,
            result,
        )

    # BTN frame 0040 is intentionally allowed to wake.
    # It demonstrates why the gate is NOT semantic authority:
    # motion wakes recognition; recognition determines whether
    # a trusted quantitative transition actually exists.
    noisy = motion(
        40,
        "seat_lower_right",
    )

    print()
    print(
        "===== NON-SEMANTIC WAKE EXAMPLE ====="
    )
    print(
        "0040 seat_lower_right",
        f"fraction={noisy.changed_fraction:.4f}",
        f"mean={noisy.mean_diff:.2f}",
        f"wake={noisy.wake}",
    )

    assert noisy.wake

    print()
    print(
        "PASS: cheap motion gate wakes every known "
        "quantitative action and remains non-semantic"
    )


if __name__ == "__main__":
    main()
