from pathlib import Path
import json
import cv2
import pytesseract

ROOT = Path(__file__).resolve().parents[2]
GEOM = json.loads((ROOT / "config/geometry.json").read_text())

captures = sorted((ROOT / "runtime/window_captures").glob("acr_table_*.png"))
if not captures:
    raise SystemExit("No captures found in runtime/window_captures")

img_path = captures[-1]
img = cv2.imread(str(img_path))
img = cv2.resize(img, (934, 696))

out = img.copy()

debug_dir = ROOT / "runtime" / "debug"
debug_dir.mkdir(parents=True, exist_ok=True)

print("Capture:", img_path)
print()

for name, rect in GEOM["action_buttons"].items():
    x = rect["x"]
    y = rect["y"]
    w = rect["width"]
    h = rect["height"]

    crop = img[y:y+h, x:x+w]

    if crop.size == 0:
        print(name, "EMPTY")
        continue

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)

    mean = gray.mean()
    std = gray.std()
    bright50 = (gray > 50).mean()
    bright70 = (gray > 70).mean()
    bright90 = (gray > 90).mean()
    edge_density = (edges > 0).mean()

    ocr = pytesseract.image_to_string(
        gray,
        config="--psm 7"
    ).strip()

    print("=" * 60)
    print(name)
    print(f"Rect          : {rect}")
    print(f"Mean          : {mean:.2f}")
    print(f"Std Dev       : {std:.2f}")
    print(f"Bright > 50   : {bright50:.3f}")
    print(f"Bright > 70   : {bright70:.3f}")
    print(f"Bright > 90   : {bright90:.3f}")
    print(f"Edge Density  : {edge_density:.3f}")
    print(f"OCR           : {ocr!r}")
    print()

    cv2.rectangle(out, (x, y), (x+w, y+h), (0,255,0), 2)
    cv2.putText(
        out,
        name,
        (x, y-5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0,255,0),
        1,
        cv2.LINE_AA
    )

    cv2.imwrite(str(debug_dir / f"{name}.png"), crop)

annotated = debug_dir / "action_button_debug.png"
cv2.imwrite(str(annotated), out)

print("=" * 60)
print("Annotated image:", annotated)
print("Individual crops:", debug_dir)
