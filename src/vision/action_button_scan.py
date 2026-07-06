from pathlib import Path
import subprocess
import time
import cv2

ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = ROOT / "src/vision/window_capture.py"
DEBUG = ROOT / "runtime/debug"
DEBUG.mkdir(parents=True, exist_ok=True)

print("Scanning for 20 seconds. Play normally. I will sample the lower table area repeatedly.")

best = []

for i in range(40):
    subprocess.run(["python3", str(CAPTURE_SCRIPT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    captures = sorted((ROOT / "runtime/window_captures").glob("acr_table_*.png"))
    if not captures:
        time.sleep(0.5)
        continue

    img_path = captures[-1]
    img = cv2.imread(str(img_path))
    img = cv2.resize(img, (934, 696))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    candidates = []
    for y in range(470, 680, 5):
        for x in range(250, 930, 5):
            crop = gray[y:y+55, x:x+150]
            if crop.shape != (55, 150):
                continue
            mean = float(crop.mean())
            bright = float((crop > 70).mean())
            edges = cv2.Canny(crop, 80, 160)
            edge_density = float((edges > 0).mean())

            score = mean * bright * (1 + edge_density)
            if bright > 0.08 and mean > 35:
                candidates.append((score, mean, bright, edge_density, x, y))

    if candidates:
        top = sorted(candidates, reverse=True)[0]
        score, mean, bright, edge_density, x, y = top
        best.append((score, mean, bright, edge_density, x, y, img_path))
        print(f"{i:02d}: best x={x} y={y} mean={mean:.1f} bright70={bright:.3f} edge={edge_density:.3f} file={img_path.name}")
    else:
        print(f"{i:02d}: no bright lower-ui candidate")

    time.sleep(0.5)

print()
print("TOP RESULTS")
print("-----------")
for score, mean, bright, edge_density, x, y, img_path in sorted(best, reverse=True)[:20]:
    print(f"x={x} y={y} w=150 h=55 mean={mean:.1f} bright70={bright:.3f} edge={edge_density:.3f} file={img_path.name}")

if best:
    score, mean, bright, edge_density, x, y, img_path = sorted(best, reverse=True)[0]
    img = cv2.imread(str(img_path))
    img = cv2.resize(img, (934, 696))
    cv2.rectangle(img, (x, y), (x+150, y+55), (0, 255, 0), 2)
    out = DEBUG / "best_action_candidate.png"
    cv2.imwrite(str(out), img)
    print()
    print("Best annotated image:", out)
