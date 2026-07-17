from pathlib import Path
import json
import shutil
import cv2

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.api.seat_crop_builder import load_geometry

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_DIR = ROOT / "runtime/validation/dealer_positions/captures"
GEOMETRY_PATH = ROOT / "config/geometry.json"
BACKUP_PATH = ROOT / "config/geometry.json.before_click_dealer_calibration"

SEAT_ORDER = [
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
]

captures = sorted(
    CAPTURE_DIR.glob("*.png"),
    key=lambda p: p.stat().st_mtime,
)

if len(captures) != 8:
    raise SystemExit(f"Expected 8 captures, found {len(captures)}")

geometry = load_geometry()
centers = {}

window_name = "Dealer Calibration"

for index, (path, seat) in enumerate(zip(captures, SEAT_ORDER), start=1):
    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"Could not read {path}")

    image = to_canonical_frame(image, geometry)
    display = image.copy()
    clicked = []

    cv2.putText(
        display,
        f"{index}/8 {seat}: click center of white D",
        (15, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked[:] = [(x, y)]

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 934, 696)
    cv2.setMouseCallback(window_name, on_mouse)

    while True:
        preview = display.copy()

        if clicked:
            x, y = clicked[0]
            cv2.drawMarker(
                preview,
                (x, y),
                (0, 0, 255),
                cv2.MARKER_CROSS,
                24,
                2,
            )

        cv2.imshow(window_name, preview)
        key = cv2.waitKey(20) & 0xFF

        if key in (13, 32) and clicked:
            break

        if key == 27:
            cv2.destroyAllWindows()
            raise SystemExit("Calibration cancelled")

    centers[seat] = {
        "x": clicked[0][0],
        "y": clicked[0][1],
    }

cv2.destroyAllWindows()

if not BACKUP_PATH.exists():
    shutil.copy2(GEOMETRY_PATH, BACKUP_PATH)

raw = json.loads(GEOMETRY_PATH.read_text())

zone_width = 64
zone_height = 52

raw["dealer_button_centers"] = centers
raw["dealer_button_zones"] = {
    seat: {
        "x": center["x"] - zone_width // 2,
        "y": center["y"] - zone_height // 2,
        "width": zone_width,
        "height": zone_height,
    }
    for seat, center in centers.items()
}

raw["geometry_version"] = "v0.11.2-click-calibrated-dealer"

GEOMETRY_PATH.write_text(json.dumps(raw, indent=2) + "\n")

print("Saved exact dealer centers:")
print(json.dumps(centers, indent=2))
print()
print("Updated:", GEOMETRY_PATH)
print("Backup:", BACKUP_PATH)
