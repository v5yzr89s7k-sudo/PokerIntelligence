from pathlib import Path
import json
import shutil
import cv2
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.api.seat_crop_builder import load_geometry

GEOMETRY_PATH = ROOT / "config" / "geometry.json"
BACKUP_PATH = ROOT / "config" / "geometry.json.before_geometry_calibration"

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

WINDOW = "Poker Intelligence Geometry Calibration"


def latest_capture():
    captures = sorted(
        (ROOT / "runtime/window_captures").glob("acr_table_*.png"),
        key=lambda p: p.stat().st_mtime,
    )
    if not captures:
        raise SystemExit("No window capture found.")
    return captures[-1]


def load_image():
    geometry = load_geometry()

    desktop = Path.home() / "Desktop"
    matches = sorted(
        desktop.glob("Screenshot 2026-07-19 at 11.28.35*AM.png"),
        key=lambda path: path.stat().st_mtime,
    )

    if not matches:
        raise SystemExit(
            "Could not find Screenshot 2026-07-19 at 11.28.35 AM.png "
            "on the Desktop."
        )

    path = matches[-1]
    print(f"Using calibration image: {path}")

    image = cv2.imread(str(path))
    if image is None:
        raise SystemExit(f"Unable to read calibration image: {path}")

    return to_canonical_frame(image, geometry)


def load_json():
    return json.loads(GEOMETRY_PATH.read_text())


def save_json(data):
    if not BACKUP_PATH.exists():
        shutil.copy2(GEOMETRY_PATH, BACKUP_PATH)
    GEOMETRY_PATH.write_text(json.dumps(data, indent=2) + "\n")


def choose_mode():
    print()
    print("Poker Intelligence Geometry Calibration")
    print()
    print("1. Dealer Button")
    print("2. Bet Regions")
    print("3. Stack Regions")
    print()

    choice = input("Selection: ").strip()

    if choice == "1":
        return "dealer_button_zones"

    if choice == "2":
        return "bet_regions"

    if choice == "3":
        return "stack_regions"

    raise SystemExit("Invalid selection.")

def calibrate_dealer(image):
    centers = {}

    for i, seat in enumerate(SEAT_ORDER, start=1):
        frame = image.copy()

        cv2.putText(
            frame,
            f"{i}/8 {seat} - Click dealer button center",
            (15, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0,255,255),
            2,
        )

        clicked = []

        def mouse(event,x,y,flags,param):
            if event == cv2.EVENT_LBUTTONDOWN:
                clicked[:] = [(x,y)]

        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW,934,696)
        cv2.setMouseCallback(WINDOW,mouse)

        while True:
            preview = frame.copy()

            if clicked:
                cv2.drawMarker(
                    preview,
                    clicked[0],
                    (0,0,255),
                    cv2.MARKER_CROSS,
                    24,
                    2,
                )

            cv2.imshow(WINDOW,preview)

            key = cv2.waitKey(20) & 0xff

            if key in (13,32) and clicked:
                break

            if key == 27:
                raise SystemExit("Cancelled.")

        x,y = clicked[0]

        centers[seat]={
            "x":x,
            "y":y,
        }

    cv2.destroyAllWindows()

    geometry=load_json()

    geometry["dealer_button_zones"]={
        seat:{
            "x":c["x"]-32,
            "y":c["y"]-26,
            "width":64,
            "height":52,
        }
        for seat,c in centers.items()
    }

    save_json(geometry)


def calibrate_regions(image, section):

    geometry = load_json()

    geometry.setdefault(section, {})

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, 934, 696)

    for i, seat in enumerate(SEAT_ORDER, start=1):

        frame = image.copy()

        cv2.putText(
            frame,
            f"{i}/8 {seat} - Drag ROI then ENTER",
            (15,35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0,255,255),
            2,
        )

        roi = cv2.selectROI(
            WINDOW,
            frame,
            showCrosshair=True,
            fromCenter=False,
        )

        x,y,w,h = map(int, roi)

        if w <= 0 or h <= 0:
            raise SystemExit("Cancelled.")

        geometry[section][seat] = {
            "x": x,
            "y": y,
            "width": w,
            "height": h,
        }

        print(f"Saved {seat}")

    cv2.destroyAllWindows()

    save_json(geometry)


def main():

    image = load_image()

    mode = choose_mode()

    if mode == "dealer_button_zones":
        calibrate_dealer(image)
    else:
        calibrate_regions(image, mode)

    print()
    print("Geometry updated successfully.")
    print(GEOMETRY_PATH)


if __name__ == "__main__":
    main()

