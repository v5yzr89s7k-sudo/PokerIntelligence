from pathlib import Path
import json
import cv2
import subprocess
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOMETRY = ROOT / "config/geometry.json"
OUT = ROOT / "runtime/card_harvest"
OUT.mkdir(parents=True, exist_ok=True)

g = json.load(open(GEOMETRY))
hero_cards = g["hero_cards"]

def latest_capture():
    return sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]

def crop(img, r):
    x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])
    return img[y:y+h, x:x+w]

def card_present(c):
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    return (gray > 145).mean() > 0.08

print("=" * 60)
print("Card Template Harvester")
print("=" * 60)
print("Keep ACR open. This saves hero card crops whenever cards appear.")
print("Press Ctrl+C to stop.")
print(f"Saving to: {OUT}")
print("=" * 60)

seen = set()
frame = 0

try:
    while True:
        frame += 1
        subprocess.run(["python3", str(CAPTURE_SCRIPT)], cwd=str(ROOT),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        img = cv2.imread(str(latest_capture()))
        img = cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)

        saved = []
        for name, region in hero_cards.items():
            c = crop(img, region)
            if not card_present(c):
                continue

            gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (20, 30))
            sig = (name, small.tobytes())

            if sig in seen:
                continue

            seen.add(sig)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = OUT / f"{ts}_frame{frame:04d}_{name}_LABEL_ME.png"
            cv2.imwrite(str(path), c)
            saved.append(path.name)

        if saved:
            print("Saved:", ", ".join(saved))

        time.sleep(0.35)

except KeyboardInterrupt:
    print()
    print(f"Stopped. Harvested {len(list(OUT.glob('*.png')))} card crops.")
