from pathlib import Path
import json
import cv2

ROOT = Path(__file__).resolve().parents[2]

GEOMETRY = ROOT / "config/geometry.json"
IMAGE = ROOT / "runtime/dealer_recalibration/canonical_full.png"

geometry = json.loads(GEOMETRY.read_text())
zones = geometry["dealer_button_zones"]

img = cv2.imread(str(IMAGE))
if img is None:
    raise SystemExit("Missing canonical_full.png")

selected = list(zones.keys())[0]
step = 2

def draw():
    canvas = img.copy()

    for seat, r in zones.items():
        color = (0,255,255)
        thick = 3 if seat == selected else 1

        cv2.rectangle(
            canvas,
            (r["x"], r["y"]),
            (r["x"]+r["width"], r["y"]+r["height"]),
            color,
            thick,
        )

        cv2.putText(
            canvas,
            seat,
            (r["x"], r["y"]-4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )

    cv2.imshow("Dealer Zone Calibration", canvas)

draw()

while True:

    k = cv2.waitKey(0)

    keys = list(zones.keys())

    if k == ord(']'):
        selected = keys[(keys.index(selected)+1)%len(keys)]
        draw()

    elif k == ord('['):
        selected = keys[(keys.index(selected)-1)%len(keys)]
        draw()

    elif k == 81:
        zones[selected]["x"] -= step

    elif k == 83:
        zones[selected]["x"] += step

    elif k == 82:
        zones[selected]["y"] -= step

    elif k == 84:
        zones[selected]["y"] += step

    elif k == ord('w'):
        zones[selected]["height"] -= step

    elif k == ord('s'):
        zones[selected]["height"] += step

    elif k == ord('a'):
        zones[selected]["width"] -= step

    elif k == ord('d'):
        zones[selected]["width"] += step

    elif k == ord('p'):
        GEOMETRY.write_text(json.dumps(geometry, indent=2))
        print("Saved geometry.json")

    elif k == 27:
        break

    draw()

cv2.destroyAllWindows()
