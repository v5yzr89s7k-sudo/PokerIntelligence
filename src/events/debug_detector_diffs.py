from pathlib import Path
import json
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GEOM = json.load(open(ROOT / "config/geometry.json"))
CAPTURES = sorted((ROOT / "runtime/window_captures").glob("acr_table_*.png"))

if len(CAPTURES) < 2:
    raise SystemExit("Need at least 2 captures")

a = cv2.imread(str(CAPTURES[-2]))
b = cv2.imread(str(CAPTURES[-1]))

def mean_diff(rect):
    x,y,w,h = map(int, [rect["x"], rect["y"], rect["width"], rect["height"]])
    return float(np.mean(cv2.absdiff(a[y:y+h,x:x+w], b[y:y+h,x:x+w])))

for group in ["hero_cards", "board", "pot_region", "action_buttons", "stack_regions", "dealer_button_zones"]:
    print("\n" + group)
    for name, rect in GEOM[group].items():
        print(name, round(mean_diff(rect), 2))
