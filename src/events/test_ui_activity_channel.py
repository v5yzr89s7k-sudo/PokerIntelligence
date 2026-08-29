import numpy as np

from src.events.local_event_detector import (
    LocalEventDetector,
    GEOM,
)


def frame():
    return np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )


def main():
    detector = LocalEventDetector()

    previous = frame()
    current = frame()

    rect = GEOM["stack_regions"]["hero"]

    x = int(rect["x"])
    y = int(rect["y"])
    w = int(rect["width"])
    h = int(rect["height"])

    # Deterministic bottom-strip-only animation.
    current[
        y + h - 7:y + h,
        x:x + w,
        :
    ] = 30

    detector.previous_frame = previous

    changes = detector.detect(
        current
    )

    print(
        "stack_changed_seats:",
        changes.stack_changed_seats,
    )

    print(
        "ui_activity_seats:",
        getattr(
            changes,
            "ui_activity_seats",
            None,
        ),
    )

    # Phase 1 is observational only:
    # legacy stack motion must remain untouched.
    assert "hero" in changes.stack_changed_seats, (
        "REGRESSION: observational UI channel changed "
        "legacy stack semantics"
    )

    assert getattr(
        changes,
        "ui_activity_seats",
        [],
    ) == ["hero"], (
        "RED: bottom-strip UI animation has no independent "
        "physical activity channel"
    )

    print(
        "PASS UI activity transport: deterministic bottom-strip "
        "motion is independently observable without changing "
        "legacy stack semantics"
    )


if __name__ == "__main__":
    main()
