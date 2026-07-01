from pathlib import Path
import json
import cv2
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOMETRY = ROOT / "config/geometry.json"
OUT = ROOT / "runtime/hole_cards_overlay.png"

subprocess.run(["python3", str(CAPTURE_SCRIPT)], cwd=str(ROOT), check=True)

latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
img = cv2.imread(str(latest))
img = cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)

g = json.load(open(GEOMETRY))

for seat, cards in g.get("hole_cards", {}).items():
    for card_name, r in cards.items():
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])
        cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(img, f"{seat}:{card_name}", (x, max(14, y-5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,255,0), 1)

cv2.imwrite(str(OUT), img)
print(f"Saved {OUT}")
