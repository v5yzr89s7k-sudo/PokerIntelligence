"""
RED contract for generic stack-motion retry lifetime.

A generic physical stack-motion wake may schedule quantitative OCR.

But if that OCR resolves exactly to the trusted baseline and there is
no independently confirmed commitment, generic stack_motion ownership
must not repeatedly force synchronous OCR across many quiet frames.

This contract deliberately does NOT apply to explicit
hero_action_completion ownership, whose delayed-transition behavior
is protected independently.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "src/v017/frame_hand_observer.py"
).read_text()


def main():
    print(
        "===== GENERIC STACK-MOTION SAME-BASELINE "
        "RETRY CONTRACT ====="
    )

    start = SOURCE.index(
        "same_baseline_retry = bool("
    )

    end = SOURCE.index(
        "elif (",
        start,
    )

    block = SOURCE[start:end]

    print()
    print(
        "generic stack_motion explicitly allowed "
        "to retain same-baseline retry:",
        'retry_reason == "stack_motion"' in block,
    )

    print(
        "hero completion explicitly allowed:",
        "hero_completion_retry" in block,
    )

    assert "hero_completion_retry" in block

    assert (
        'retry_reason == "stack_motion"'
        not in block
    ), (
        "generic stack_motion still owns repeated "
        "same-baseline synchronous OCR"
    )

    print()
    print(
        "HERO COMPLETION RETRY PRESERVED: YES"
    )
    print(
        "GENERIC SAME-BASELINE RETRY LOOP: NO"
    )
    print(
        "V0.17 GENERIC STACK-MOTION RETRY "
        "LIFETIME: PASS"
    )


if __name__ == "__main__":
    main()
