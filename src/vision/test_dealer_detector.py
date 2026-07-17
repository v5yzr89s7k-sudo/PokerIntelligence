from pathlib import Path
import json
import sys

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.vision.dealer_detector import detect_dealer_button

CAPTURE_DIR = ROOT / "runtime/validation/dealer_positions/captures"
GROUND_TRUTH_PATH = (
    ROOT / "runtime/validation/dealer_positions/ground_truth.json"
)
GEOMETRY_PATH = ROOT / "config/geometry.json"
TEMPLATE_PATH = ROOT / "assets/templates/dealer_button_calibrated.png"

captures = sorted(
    CAPTURE_DIR.glob("*.png"),
    key=lambda path: path.stat().st_mtime,
)

ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
geometry = json.loads(GEOMETRY_PATH.read_text())

if len(captures) != 8:
    raise SystemExit(f"Expected 8 captures, found {len(captures)}")

# Build the template from the precisely clicked dealer center in Frame 1.
source = cv2.imread(str(captures[0]))
if source is None:
    raise SystemExit(f"Could not read {captures[0]}")

source = to_canonical_frame(source, geometry)

seat = ground_truth[captures[0].name]
center = geometry["dealer_button_centers"][seat]

cx = int(center["x"])
cy = int(center["y"])

template_width = 34
template_height = 28

x1 = cx - template_width // 2
y1 = cy - template_height // 2
x2 = x1 + template_width
y2 = y1 + template_height

template = source[y1:y2, x1:x2].copy()

if template.shape[:2] != (template_height, template_width):
    raise SystemExit(f"Invalid template shape: {template.shape}")

TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)

if not cv2.imwrite(str(TEMPLATE_PATH), template):
    raise SystemExit(f"Could not write {TEMPLATE_PATH}")

print("=" * 72)
print("Dealer detector validation")
print("=" * 72)
print("Template:", TEMPLATE_PATH)
print()

passed = 0

for index, path in enumerate(captures, start=1):
    expected = ground_truth[path.name]
    result = detect_dealer_button(path)
    detected = result["dealer_button_seat"]
    best = result["best"]

    ok = detected == expected
    passed += int(ok)

    print(
        f"Frame {index}: {'PASS' if ok else 'FAIL'} "
        f"expected={expected} detected={detected} "
        f"score={best['score']:.4f} "
        f"template={best['confidence']:.4f}"
    )

print()
print(f"Accuracy: {passed} / {len(captures)}")

if passed != len(captures):
    raise SystemExit(1)
