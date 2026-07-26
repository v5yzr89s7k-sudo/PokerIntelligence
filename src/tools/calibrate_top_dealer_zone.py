from pathlib import Path
import json
import cv2

ROOT = Path(__file__).resolve().parents[2]

IMAGE = ROOT / "runtime/dealer_recalibration/canonical_full.png"
GEOMETRY = ROOT / "config/geometry.json"

img = cv2.imread(str(IMAGE))
if img is None:
    raise SystemExit("Missing canonical_full.png")

geometry = json.loads(GEOMETRY.read_text())

zone = geometry["dealer_button_zones"]["seat_top"]

STEP = 2

while True:

    canvas = img.copy()

    cv2.rectangle(
        canvas,
        (zone["x"], zone["y"]),
        (zone["x"] + zone["width"], zone["y"] + zone["height"]),
        (0,255,255),
        2,
    )

    cv2.putText(
        canvas,
        "seat_top",
        (zone["x"], zone["y"]-5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0,255,255),
        2,
    )

    cv2.imshow("Top Dealer Calibration", canvas)

    key = cv2.waitKey(0) & 0xff

    if key == 27:
        break

    elif key == ord("j"):
        zone["x"] -= STEP

    elif key == ord("l"):
        zone["x"] += STEP

    elif key == ord("i"):
        zone["y"] -= STEP

    elif key == ord("k"):
        zone["y"] += STEP

    elif key == ord("p"):
        GEOMETRY.write_text(json.dumps(geometry, indent=2))
        print("Saved.")

cv2.destroyAllWindows()
