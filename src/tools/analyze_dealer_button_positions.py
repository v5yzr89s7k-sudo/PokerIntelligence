from pathlib import Path
import json
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.canonical_frame import to_canonical_frame
from src.vision.dealer_detector import normalize_patch

ROOT = Path(__file__).resolve().parents[2]

GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)

TEMPLATE = cv2.imread(
    str(ROOT / "assets/templates/dealer_button_calibrated.png")
)

if TEMPLATE is None:
    raise SystemExit("Dealer template not found.")

template = normalize_patch(TEMPLATE)
th, tw = template.shape[:2]

captures = sorted(
    (ROOT / "runtime/window_captures").glob("*.png")
)

OUT = ROOT / "runtime/dealer_analysis"
OUT.mkdir(parents=True, exist_ok=True)

SEARCH_MARGIN = 120

summary = {}

print(f"Scanning {len(captures)} captures...\n")

for seat, zone in GEOMETRY["dealer_button_zones"].items():

    zx = int(zone["x"])
    zy = int(zone["y"])
    zw = int(zone["width"])
    zh = int(zone["height"])

    points = []

    canvas = np.zeros((696, 934, 3), dtype=np.uint8)

    for frame_path in captures:

        img = cv2.imread(str(frame_path))
        if img is None:
            continue

        img = to_canonical_frame(img, GEOMETRY)

        x0 = max(0, zx - SEARCH_MARGIN)
        y0 = max(0, zy - SEARCH_MARGIN)
        x1 = min(img.shape[1], zx + zw + SEARCH_MARGIN)
        y1 = min(img.shape[0], zy + zh + SEARCH_MARGIN)

        crop = img[y0:y1, x0:x1]

        gray = normalize_patch(crop)

        if gray.shape[0] < th or gray.shape[1] < tw:
            continue

        result = cv2.matchTemplate(
            gray,
            template,
            cv2.TM_CCOEFF_NORMED,
        )

        _, score, _, loc = cv2.minMaxLoc(result)

        if score < 0.30:
            continue

        px = x0 + loc[0]
        py = y0 + loc[1]

        points.append((px, py, score))

        cv2.circle(
            canvas,
            (px, py),
            2,
            (0,255,255),
            -1,
        )

    if not points:
        print(f"{seat:18} no matches")
        continue

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    rx = min(xs)
    ry = min(ys)
    rw = max(xs) - rx + tw
    rh = max(ys) - ry + th

    cv2.rectangle(
        canvas,
        (rx, ry),
        (rx + rw, ry + rh),
        (0,255,0),
        2,
    )

    cv2.imwrite(
        str(OUT / f"{seat}_heatmap.png"),
        canvas,
    )

    summary[seat] = {
        "matches": len(points),
        "recommended_zone": {
            "x": int(rx),
            "y": int(ry),
            "width": int(rw),
            "height": int(rh),
        },
    }

    print(
        f"{seat:18} matches={len(points):4d} "
        f"recommended=({rx},{ry},{rw},{rh})"
    )

(OUT / "dealer_zone_statistics.json").write_text(
    json.dumps(summary, indent=2)
)

print("\nDone.")
print("Results written to:", OUT)
