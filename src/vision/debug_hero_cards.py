from pathlib import Path
import json
import cv2
import subprocess
import pytesseract

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOMETRY = ROOT / "config/geometry.json"
OUT = ROOT / "runtime/card_debug/hero"
OUT.mkdir(parents=True, exist_ok=True)

subprocess.run(["python3", str(CAPTURE_SCRIPT)], cwd=str(ROOT), check=True)

latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
img = cv2.imread(str(latest))
img = cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)

g = json.load(open(GEOMETRY))
cards = g["hero_cards"]

def crop(r):
    x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])
    return img[y:y+h, x:x+w]

def preprocess(c):
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    big = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    th = cv2.threshold(big, 145, 255, cv2.THRESH_BINARY)[1]
    return big, th

for name, region in cards.items():
    c = crop(region)
    big, th = preprocess(c)

    cv2.imwrite(str(OUT / f"{name}_raw.png"), c)
    cv2.imwrite(str(OUT / f"{name}_big.png"), big)
    cv2.imwrite(str(OUT / f"{name}_threshold.png"), th)

    raw_rank = pytesseract.image_to_string(
        th,
        config="--psm 10 -c tessedit_char_whitelist=AKQJT98765432"
    ).strip()

    raw_text = pytesseract.image_to_string(
        th,
        config="--psm 7 -c tessedit_char_whitelist=AKQJT9876543210"
    ).strip()

    print(f"{name}: psm10={raw_rank!r} psm7={raw_text!r}")

print(f"Saved hero card debug crops to {OUT}")
