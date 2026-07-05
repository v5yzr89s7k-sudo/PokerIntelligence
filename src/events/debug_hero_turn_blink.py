from pathlib import Path
import json, subprocess, sys, time
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CAPTURE = ROOT / "src/vision/window_capture.py"
GEOM = json.load(open(ROOT / "config/geometry.json"))
RECT = GEOM["stack_regions"]["hero"]

def capture_frame():
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    latest = sorted((ROOT / "runtime/window_captures").glob("acr_table_*.png"))[-1]
    img = cv2.imread(str(latest))
    return cv2.resize(img, (934, 696))

def crop_gray(img):
    x,y,w,h = RECT["x"],RECT["y"],RECT["width"],RECT["height"]
    c = img[y:y+h, x:x+w]
    return cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)

print("Press ENTER while Hero nameplate is blinking.")
input()

frames = []
for i in range(16):
    frames.append(crop_gray(capture_frame()))
    time.sleep(0.15)

diffs = [float(np.mean(cv2.absdiff(frames[i-1], frames[i]))) for i in range(1, len(frames))]
means = [float(np.mean(f)) for f in frames]

for i, (m, d) in enumerate(zip(means[1:], diffs), start=2):
    print(f"{i:02d} mean={m:.2f} diff={d:.2f}")

print("max_diff=", max(diffs))
print("mean_range=", max(means) - min(means))
print("blink_detected=", max(diffs) >= 5.0 or (max(means) - min(means)) >= 5.0)
