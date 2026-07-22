from pathlib import Path
import json
import re
import sys
import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vision.stack_reader import read_stack

GEOMETRY = json.loads((ROOT / "config/geometry.json").read_text())

LOWER_GREEN = (35, 30, 60)
UPPER_GREEN = (95, 255, 255)


def local_stack_ocr(img, region):
    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[y:y+h, x:x+w]
    result = read_stack(crop)

    value = result["stack_bb"]

    if value is None:
        return ""

    return f"{value:g}"


frames = sorted(
    (ROOT / "runtime/window_captures").glob("acr_table_*.png")
)

# Sample across the full capture history.
if len(frames) > 100:
    step = max(1, len(frames) // 100)
    frames = frames[::step]

print(f"Sampled frames: {len(frames)}")
print("This benchmark is local-only.")
print("It does not claim accuracy without labels.")
print()

for frame in frames:
    img = cv2.imread(str(frame))

    if img is None:
        continue

    img = cv2.resize(
        img,
        (934, 696),
    )

    print(f"\n=== {frame.name} ===")

    for seat, region in GEOMETRY["stack_regions"].items():
        got = local_stack_ocr(
            img,
            region,
        )

        print(
            f"{seat:16} {got or '-'}"
        )

