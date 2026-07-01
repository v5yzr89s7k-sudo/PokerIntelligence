from pathlib import Path
import json
import cv2
import subprocess
from src.vision.card_recognizer import read_card

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOMETRY = ROOT / "config/geometry.json"

subprocess.run(["python3", str(CAPTURE_SCRIPT)], cwd=str(ROOT), check=True)

latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
img = cv2.imread(str(latest))
img = cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)

g = json.load(open(GEOMETRY))
cards = g["hero_cards"]

def crop(r):
    x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])
    return img[y:y+h, x:x+w]

c1 = read_card(crop(cards["card_1"]))
c2 = read_card(crop(cards["card_2"]))

print("=" * 50)
print("Hero Card Reader")
print("=" * 50)
print(f"Card 1: {c1}")
print(f"Card 2: {c2}")
print()
print(f"Hero Hand: {c1['card']} {c2['card']}")
print("=" * 50)
