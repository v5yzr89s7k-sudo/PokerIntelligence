from pathlib import Path
import json
import cv2
import pytesseract
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REPLAY_DIR = ROOT / "runtime/replay"
GEOMETRY = ROOT / "config/geometry.json"
INSPECT_DIR = ROOT / "runtime/frame_inspector"
INSPECT_DIR.mkdir(parents=True, exist_ok=True)

frames = sorted(REPLAY_DIR.glob("frame_*.png"))
if not frames:
    raise SystemExit("No replay frames found in runtime/replay")

geometry = json.load(open(GEOMETRY))

GROUPS = [
    "stack_regions",
    "bet_regions",
    "pot_region",
    "hero_cards",
    "board",
    "dealer_button_zones",
    "action_buttons",
]

COLORS = {
    "stack_regions": (0, 0, 255),
    "bet_regions": (255, 0, 0),
    "pot_region": (255, 255, 0),
    "hero_cards": (0, 255, 0),
    "board": (0, 255, 255),
    "dealer_button_zones": (255, 0, 255),
    "action_buttons": (255, 255, 255),
}

idx = 0
zoom = 1.0
mode = "all"
regions_on_screen = []


def ocr_region(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    gray = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)[1]
    return pytesseract.image_to_string(gray, config="--psm 7").strip()


def active_groups():
    if mode == "all":
        return GROUPS
    return [mode]


def current_img():
    img = cv2.imread(str(frames[idx]))
    return cv2.resize(img, (934, 696), interpolation=cv2.INTER_AREA)


def draw_overlay(img):
    global regions_on_screen
    regions_on_screen = []
    out = img.copy()

    for group in active_groups():
        color = COLORS[group]
        for name, r in geometry.get(group, {}).items():
            try:
                x = int(r["x"])
                y = int(r["y"])
                w = int(r["width"])
                h = int(r["height"])
            except Exception:
                continue

            regions_on_screen.append((group, name, x, y, w, h))
            cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
            label = f"{name}"
            cv2.putText(
                out,
                label,
                (x, max(14, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    cv2.putText(
        out,
        f"{frames[idx].name} [{idx+1}/{len(frames)}] mode={mode} zoom={zoom:.1f}",
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    return out


def inspect_region(group, name, x, y, w, h):
    img = current_img()
    crop = img[y:y+h, x:x+w]
    text = ocr_region(crop)

    crop_path = INSPECT_DIR / f"{frames[idx].stem}__{group}__{name}.png"
    cv2.imwrite(str(crop_path), crop)

    print()
    print("=" * 70)
    print("REGION INSPECTED")
    print(f"Frame: {frames[idx].name}")
    print(f"Group: {group}")
    print(f"Name: {name}")
    print(f"Coords: x={x}, y={y}, width={w}, height={h}")
    print(f"OCR: {text!r}")
    print(f"Crop saved: {crop_path}")
    print("=" * 70)

    big = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST)
    cv2.imshow("Selected Region Crop", big)


def mouse_callback(event, mx, my, flags, param):
    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # Convert screen click back to normalized table coords
    x_click = int(mx / zoom)
    y_click = int(my / zoom)

    for group, name, x, y, w, h in reversed(regions_on_screen):
        if x <= x_click <= x + w and y <= y_click <= y + h:
            inspect_region(group, name, x, y, w, h)
            return


def render():
    img = draw_overlay(current_img())
    if zoom != 1.0:
        img = cv2.resize(img, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)
    return img


print("=" * 70)
print("Poker Intelligence Replay Browser + Frame Inspector")
print("=" * 70)
print("Keys:")
print("  Right arrow / d = next frame")
print("  Left arrow / a  = previous frame")
print("  0 = show all")
print("  1 = stacks only")
print("  2 = bets only")
print("  3 = pot only")
print("  4 = hero cards only")
print("  5 = board only")
print("  6 = dealer only")
print("  7 = action buttons only")
print("  + / = = zoom in")
print("  -     = zoom out")
print("  Click any rectangle to inspect crop + OCR")
print("  q / Esc = quit")
print("=" * 70)

cv2.namedWindow("Poker Intelligence Replay Browser")
cv2.setMouseCallback("Poker Intelligence Replay Browser", mouse_callback)

while True:
    cv2.imshow("Poker Intelligence Replay Browser", render())
    key = cv2.waitKeyEx(0)

    if key in [27, ord("q")]:
        break
    elif key in [83, ord("d")]:
        idx = min(len(frames) - 1, idx + 1)
    elif key in [81, ord("a")]:
        idx = max(0, idx - 1)
    elif key == ord("0"):
        mode = "all"
    elif key == ord("1"):
        mode = "stack_regions"
    elif key == ord("2"):
        mode = "bet_regions"
    elif key == ord("3"):
        mode = "pot_region"
    elif key == ord("4"):
        mode = "hero_cards"
    elif key == ord("5"):
        mode = "board"
    elif key == ord("6"):
        mode = "dealer_button_zones"
    elif key == ord("7"):
        mode = "action_buttons"
    elif key in [ord("+"), ord("=")]:
        zoom = min(3.0, zoom + 0.25)
    elif key == ord("-"):
        zoom = max(0.5, zoom - 0.25)

cv2.destroyAllWindows()
