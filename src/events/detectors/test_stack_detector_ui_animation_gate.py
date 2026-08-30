import numpy as np

from src.events.detectors.stack_detector import (
    stack_change_details,
)


GEOMETRY = {
    "stack_regions": {
        "hero": {
            "x": 0,
            "y": 0,
            "width": 120,
            "height": 35,
        },
        "villain": {
            "x": 120,
            "y": 0,
            "width": 120,
            "height": 35,
        },
    }
}


def frame():
    return np.zeros(
        (35, 240, 3),
        dtype=np.uint8,
    )


def main():
    # ========================================================
    # CASE 1
    # Bottom-strip-only Hero animation.
    #
    # This deliberately exceeds Hero's existing whole-region
    # threshold while leaving the upper 28px stack body static.
    # ========================================================

    previous = frame()
    current = frame()

    current[
        28:35,
        0:120,
        :
    ] = 30

    details = stack_change_details(
        previous,
        current,
        GEOMETRY,
    )

    hero = details["hero"]

    print(
        "Hero bottom-only:",
        hero,
    )

    assert hero["mean_diff"] > 4.0, (
        "fixture no longer exceeds legacy Hero threshold"
    )

    assert hero["changed"] is False, (
        "RED: bottom-strip-only Hero UI animation still "
        "publishes raw stack motion"
    )

    # ========================================================
    # CASE 2
    # Bottom-strip-only villain animation.
    #
    # Strong enough to exceed the ordinary 8.0 threshold.
    # ========================================================

    previous = frame()
    current = frame()

    current[
        28:35,
        120:240,
        :
    ] = 70

    details = stack_change_details(
        previous,
        current,
        GEOMETRY,
    )

    villain = details["villain"]

    print(
        "Villain bottom-only:",
        villain,
    )

    assert villain["mean_diff"] > 8.0, (
        "fixture no longer exceeds legacy villain threshold"
    )

    assert villain["changed"] is False, (
        "RED: bottom-strip-only opponent UI animation still "
        "publishes raw stack motion"
    )

    # ========================================================
    # CASE 3
    # Genuine stack-body motion must remain visible.
    # ========================================================

    previous = frame()
    current = frame()

    current[
        7:24,
        120:240,
        :
    ] = 40

    details = stack_change_details(
        previous,
        current,
        GEOMETRY,
    )

    villain = details["villain"]

    print(
        "Villain body motion:",
        villain,
    )

    assert villain["changed"] is True, (
        "REGRESSION: genuine stack-body motion was suppressed"
    )

    # ========================================================
    # CASE 4
    # Mixed body + bottom motion must remain visible.
    # ========================================================

    previous = frame()
    current = frame()

    current[
        10:24,
        0:120,
        :
    ] = 25

    current[
        28:35,
        0:120,
        :
    ] = 30

    details = stack_change_details(
        previous,
        current,
        GEOMETRY,
    )

    hero = details["hero"]

    print(
        "Hero mixed motion:",
        hero,
    )

    assert hero["changed"] is True, (
        "REGRESSION: genuine Hero stack-body motion was "
        "suppressed merely because bottom UI also changed"
    )

    print(
        "PASS stack detector UI-animation gate: "
        "pure bottom-strip animation is ignored while "
        "stack-body motion remains actionable"
    )


if __name__ == "__main__":
    main()
