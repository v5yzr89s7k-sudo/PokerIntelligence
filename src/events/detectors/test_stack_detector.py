import numpy as np

from src.events.detectors.stack_detector import (
    DEFAULT_STACK_CHANGE_THRESHOLD,
    HERO_STACK_CHANGE_THRESHOLD,
    stack_change_details,
)


def frame(value=0):
    return np.full((100, 240, 3), value, dtype=np.uint8)


geometry = {
    "stack_regions": {
        "hero": {
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 40,
        },
        "villain": {
            "x": 120,
            "y": 0,
            "width": 100,
            "height": 40,
        },
    }
}

previous = frame()
current = frame()

# Produce identical raw mean differences of 5.0 in both stack regions.
current[0:40, 0:100] = 5
current[0:40, 120:220] = 5

details = stack_change_details(
    previous,
    current,
    geometry,
)

assert HERO_STACK_CHANGE_THRESHOLD == 4.0
assert DEFAULT_STACK_CHANGE_THRESHOLD == 8.0

assert details["hero"]["mean_diff"] == 5.0
assert details["hero"]["threshold"] == 4.0
assert details["hero"]["changed"] is True

assert details["villain"]["mean_diff"] == 5.0
assert details["villain"]["threshold"] == 8.0
assert details["villain"]["changed"] is False

print("stack detector hero-threshold tests passed")
