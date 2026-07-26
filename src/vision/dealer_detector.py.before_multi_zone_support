from pathlib import Path
import json
import sys

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.canonical_frame import to_canonical_frame

GEOMETRY_PATH = PROJECT_ROOT / "config/geometry.json"
TEMPLATE_PATH = PROJECT_ROOT / "assets/templates/dealer_button_calibrated.png"
DEBUG_DIR = PROJECT_ROOT / "runtime/debug_crops/dealer"


def load_geometry():
    return json.loads(GEOMETRY_PATH.read_text())


def normalize_patch(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.equalizeHist(gray)


def detect_dealer_button(image_or_path):
    if isinstance(image_or_path, (str, Path)):
        image = cv2.imread(str(image_or_path))
        if image is None:
            raise FileNotFoundError(f"Could not read image: {image_or_path}")
    else:
        image = image_or_path

    geometry = load_geometry()
    image = to_canonical_frame(image, geometry)

    template = cv2.imread(str(TEMPLATE_PATH))
    if template is None:
        raise FileNotFoundError(
            f"Missing calibrated dealer template: {TEMPLATE_PATH}"
        )

    template_gray = normalize_patch(template)
    th, tw = template_gray.shape[:2]

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for seat, zone in geometry["dealer_button_zones"].items():
        x = int(zone["x"])
        y = int(zone["y"])
        w = int(zone["width"])
        h = int(zone["height"])

        crop = image[y:y + h, x:x + w].copy()

        if crop.shape[0] < th or crop.shape[1] < tw:
            raise ValueError(
                f"Dealer zone for {seat} is smaller than template: "
                f"zone={crop.shape[1]}x{crop.shape[0]} "
                f"template={tw}x{th}"
            )

        crop_gray = normalize_patch(crop)

        response = cv2.matchTemplate(
            crop_gray,
            template_gray,
            cv2.TM_CCOEFF_NORMED,
        )

        _, confidence, _, location = cv2.minMaxLoc(response)

        match_center_x = location[0] + tw / 2.0
        match_center_y = location[1] + th / 2.0
        zone_center_x = w / 2.0
        zone_center_y = h / 2.0

        center_distance = np.hypot(
            match_center_x - zone_center_x,
            match_center_y - zone_center_y,
        )

        max_distance = np.hypot(zone_center_x, zone_center_y)
        center_score = max(0.0, 1.0 - center_distance / max_distance)

        # Template similarity is primary; expected-center proximity breaks ties.
        score = float(confidence * 0.85 + center_score * 0.15)

        annotated = crop.copy()
        mx, my = location

        cv2.rectangle(
            annotated,
            (mx, my),
            (mx + tw, my + th),
            (0, 255, 255),
            1,
        )

        cv2.imwrite(
            str(DEBUG_DIR / f"{seat}.png"),
            annotated,
        )

        results.append({
            "seat": seat,
            "confidence": round(float(confidence), 4),
            "center_score": round(float(center_score), 4),
            "score": round(score, 4),
            "match_x": int(x + mx),
            "match_y": int(y + my),
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    best = results[0]

    return {
        "found": best["confidence"] >= 0.35,
        "dealer_button_seat": best["seat"],
        "best": best,
        "all": results,
    }


def latest_capture():
    captures = sorted(
        (PROJECT_ROOT / "runtime/window_captures").glob("acr_table_*.png")
    )

    if not captures:
        raise FileNotFoundError("No ACR captures found")

    return captures[-1]


if __name__ == "__main__":
    image_path = latest_capture()
    result = detect_dealer_button(image_path)

    print("Image:", image_path)
    print("Found:", result["found"])
    print("Dealer:", result["dealer_button_seat"])

    for item in result["all"]:
        print(
            f"{item['seat']:18} "
            f"score={item['score']:.4f} "
            f"template={item['confidence']:.4f} "
            f"center={item['center_score']:.4f}"
        )
