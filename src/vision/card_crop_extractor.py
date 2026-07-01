from pathlib import Path
import json
import cv2

ROOT = Path(__file__).resolve().parents[2]
REPLAY_DIR = ROOT / "runtime/replay"
GEOMETRY = ROOT / "config/geometry.json"
OUT = ROOT / "runtime/card_training"
(OUT / "hero").mkdir(parents=True, exist_ok=True)
(OUT / "board").mkdir(parents=True, exist_ok=True)

frames = sorted(REPLAY_DIR.glob("frame_*.png"))
geometry = json.load(open(GEOMETRY))

def crop_region(img, r):
    x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])
    return img[y:y+h, x:x+w]

saved = 0
for i, frame in enumerate(frames, start=1):
    img = cv2.imread(str(frame))
    if img is None:
        continue
    img = cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)

    for name, region in geometry.get("hero_cards", {}).items():
        crop = crop_region(img, region)
        cv2.imwrite(str(OUT / "hero" / f"frame_{i:04d}__{name}.png"), crop)
        saved += 1

    for name, region in geometry.get("board", {}).items():
        crop = crop_region(img, region)
        cv2.imwrite(str(OUT / "board" / f"frame_{i:04d}__{name}.png"), crop)
        saved += 1

print(f"Saved {saved} crops")
print(f"Hero crops: {len(list((OUT / 'hero').glob('*.png')))}")
print(f"Board crops: {len(list((OUT / 'board').glob('*.png')))}")
