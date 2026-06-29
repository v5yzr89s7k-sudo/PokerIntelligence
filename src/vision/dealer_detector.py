from pathlib import Path
import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DEBUG_DIR = RUNTIME_DIR / "debug_crops"


# Seat search zones as percentages of the cropped ACR table image.
# These are rough first-pass zones. We will tune them after seeing debug output.
DEALER_SEARCH_ZONES = {
    "seat_top":        (0.42, 0.12, 0.16, 0.18),
    "seat_upper_left": (0.16, 0.22, 0.18, 0.20),
    "seat_upper_right":(0.66, 0.22, 0.18, 0.20),
    "seat_mid_left":   (0.10, 0.42, 0.20, 0.20),
    "seat_mid_right":  (0.70, 0.42, 0.20, 0.20),
    "seat_lower_left": (0.20, 0.62, 0.20, 0.20),
    "seat_lower_right":(0.60, 0.62, 0.20, 0.20),
    "hero":            (0.42, 0.70, 0.18, 0.20),
}


def crop_pct(img, box):
    h, w = img.shape[:2]
    x, y, bw, bh = box
    x1 = int(x * w)
    y1 = int(y * h)
    x2 = int((x + bw) * w)
    y2 = int((y + bh) * h)
    return img[y1:y2, x1:x2], (x1, y1, x2, y2)


def detect_dealer_button(image_path: Path):
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for seat_name, zone in DEALER_SEARCH_ZONES.items():
        crop, coords = crop_pct(img, zone)

        # ACR dealer button is usually a bright white/gray circular marker.
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        # Low saturation + high value = white/gray objects.
        mask = cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 80, 255]))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_area = 0
        best_circle_score = 0.0

        for c in contours:
            area = cv2.contourArea(c)
            if area < 20:
                continue

            perimeter = cv2.arcLength(c, True)
            if perimeter <= 0:
                continue

            circularity = 4 * np.pi * area / (perimeter * perimeter)
            x, y, w, h = cv2.boundingRect(c)
            aspect = w / h if h else 0

            # Dealer button should be a SMALL compact circular marker.
            # Reject huge white/gray UI regions like nameplates, buttons, panels.
            if not (80 <= area <= 3500):
                continue

            if not (0.70 <= circularity <= 1.25):
                continue

            if not (0.70 <= aspect <= 1.30):
                continue

            score = float(area * circularity)
            if score > best_circle_score:
                best_circle_score = score
                best_area = area

        confidence = min(best_circle_score / 1200.0, 1.0)

        cv2.imwrite(str(DEBUG_DIR / f"dealer_zone_{seat_name}.png"), crop)

        results.append({
            "seat": seat_name,
            "confidence": round(confidence, 3),
            "best_area": round(float(best_area), 2),
            "coords": coords,
        })

    results = sorted(results, key=lambda r: r["confidence"], reverse=True)

    return {
        "found": results[0]["confidence"] >= 0.25,
        "best": results[0],
        "all": results,
    }


def latest_acr_capture() -> Path:
    files = sorted((RUNTIME_DIR / "window_captures").glob("acr_table_*.png"))
    if not files:
        raise FileNotFoundError("No acr_table_*.png files found in runtime/window_captures")
    return files[-1]


if __name__ == "__main__":
    image = latest_acr_capture()
    result = detect_dealer_button(image)

    print(f"Image: {image}")
    print(f"Found: {result['found']}")
    print(f"Best: {result['best']}")
    print("All zones:")
    for r in result["all"]:
        print(f"  {r['seat']}: confidence={r['confidence']} area={r['best_area']}")
    print(f"Debug crops written to: {DEBUG_DIR}")
