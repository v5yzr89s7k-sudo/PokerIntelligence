from src.vision.stack_reader import _parse_value


cases = [
    ("95./2 BB", None),
    ("99./2 BB", None),
    ("09.72 BB", 9.72),
    ("95.72 BB", 95.72),
    ("44.49 BB", 44.49),
    ("| 9.09 BB", 9.09),
    ("27.4 BB", 27.4),
    ("54.73", 54.73),
    ("garbage", None),
]

for raw, expected in cases:
    actual = _parse_value(raw)

    assert actual == expected, (
        raw,
        expected,
        actual,
    )

    print(repr(raw), "->", actual)

print("Stack parser malformed-token regressions passed.")

from pathlib import Path

from src.api.table_snapshot_reader_core_v2 import (
    GEOMETRY,
    _prepare,
)
from src.vision.stack_reader import read_stack


frame = Path(
    "runtime/window_captures/"
    "acr_table_20260806_122418_479893.png"
)

_, cards = _prepare(frame)

card = next(
    item
    for item in cards
    if item["seat"] == "seat_lower_right"
)

region = GEOMETRY["stack_regions"]["seat_lower_right"]
bounds = card["bounds"]

x1 = int(region["x"]) - int(bounds["x1"])
y1 = int(region["y"]) - int(bounds["y1"])
x2 = x1 + int(region["width"])
y2 = y1 + int(region["height"])

result = read_stack(
    card["image"][y1:y2, x1:x2]
)

assert result["stack_bb"] == 9.72, result
assert result["votes"] == 1, result
assert result["confidence"] == 0.80, result
assert result["mode"] == "green_only", result

print(
    "Saved-frame malformed-majority regression passed:",
    result["stack_bb"],
    result["votes"],
    result["confidence"],
)
