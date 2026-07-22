from pathlib import Path
import cv2
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vision.stack_reader import read_stack


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = json.loads((ROOT / "config/geometry.json").read_text())
CAPTURE_DIR = ROOT / "runtime/window_captures"
SESSION_ROOT = ROOT / "runtime/debug/action_sequence"

import argparse

captures = sorted(CAPTURE_DIR.glob("acr_table_*.png"))

parser = argparse.ArgumentParser()
parser.add_argument("--prev", type=int, default=-2)
parser.add_argument("--curr", type=int, default=-1)
parser.add_argument("--scan", action="store_true")
parser.add_argument("--threshold", type=float, default=0.05)
parser.add_argument("--session", default=None)

args = parser.parse_args()

if args.session:
    session_dir = SESSION_ROOT / args.session
    captures = sorted(session_dir.glob("*_full.png"))

if len(captures) < 2:
    raise SystemExit("Need at least two captures.")

if args.scan:
    last_values = None
    last_path = None

    for path in captures:
        image = cv2.imread(str(path))
        if image is None:
            continue

        image = cv2.resize(image, (934, 696))
        values = {}

        for seat, region in GEOMETRY["stack_regions"].items():
            x = int(region["x"])
            y = int(region["y"])
            w = int(region["width"])
            h = int(region["height"])

            reading = read_stack(image[y:y+h, x:x+w])
            if reading["stack_bb"] is not None:
                values[seat] = float(reading["stack_bb"])

        if last_values is not None:
            changes = []

            for seat in sorted(set(last_values) & set(values)):
                delta = round(last_values[seat] - values[seat], 2)
                if abs(delta) >= args.threshold:
                    suspicious = (
                        abs(delta) > 20.0
                        or last_values[seat] <= 5.0
                        or values[seat] <= 5.0
                    )

                    label = "SUSPICIOUS" if suspicious else "VALID_CANDIDATE"

                    changes.append(
                        f"{label} "
                        f"{seat}:{last_values[seat]:.2f}->{values[seat]:.2f} "
                        f"delta={delta:.2f}"
                    )

            if changes:
                print()
                print(last_path.name)
                print(path.name)
                for change in changes:
                    print("  ", change)

        last_values = values
        last_path = path

    raise SystemExit(0)

previous_path = captures[args.prev]
current_path = captures[args.curr]

previous = cv2.imread(str(previous_path))
current = cv2.imread(str(current_path))

previous = cv2.resize(previous, (934,696))
current = cv2.resize(current, (934,696))

print()
print("Previous:", previous_path.name)
print("Current :", current_path.name)
print()

print(f"{'Seat':<18}{'Previous':>10}{'Current':>10}{'Delta':>10}{'Conf':>8}{'Mode':>12}")
print("-"*72)

for seat, region in GEOMETRY["stack_regions"].items():
    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    prev_crop = previous[y:y+h, x:x+w]
    curr_crop = current[y:y+h, x:x+w]

    prev = read_stack(prev_crop)
    curr = read_stack(curr_crop)

    if prev["stack_bb"] is None or curr["stack_bb"] is None:
        continue

    delta = round(prev["stack_bb"] - curr["stack_bb"],2)

    print(
        f"{seat:<18}"
        f"{prev['stack_bb']:>10.2f}"
        f"{curr['stack_bb']:>10.2f}"
        f"{delta:>10.2f}"
        f"{curr['confidence']:>8.2f}"
        f"{curr['mode']:>12}"
    )
