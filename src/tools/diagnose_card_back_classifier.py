from pathlib import Path
import json
import sys

import cv2
import numpy as np

from src.api.canonical_frame import to_canonical_frame
from src.events.detectors.card_presence import SEAT_ORDER


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"
CAPTURE_DIR = ROOT / "runtime/window_captures"

OUT_JSON = (
    ROOT
    / "runtime/debug"
    / "card_back_classifier_diagnostic.json"
)

OUT_OVERLAY = (
    ROOT
    / "runtime/debug"
    / "card_back_classifier_overlay.png"
)


def crop(image, rect):
    x = int(rect["x"])
    y = int(rect["y"])
    width = int(rect["width"])
    height = int(rect["height"])

    return image[
        y:y + height,
        x:x + width,
    ].copy()


def card_back_features(image):
    if image is None or image.size == 0:
        return {
            "red_ratio": 0.0,
            "strong_red_ratio": 0.0,
            "saturated_ratio": 0.0,
            "edge_density": 0.0,
            "mean_saturation": 0.0,
            "mean_value": 0.0,
        }

    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV,
    )

    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    red_hue = (
        (hue <= 12)
        | (hue >= 168)
    )

    red_pixels = (
        red_hue
        & (saturation >= 70)
        & (value >= 35)
    )

    strong_red_pixels = (
        red_hue
        & (saturation >= 120)
        & (value >= 45)
    )

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    edges = cv2.Canny(
        gray,
        60,
        140,
    )

    return {
        "red_ratio": round(
            float(red_pixels.mean()),
            6,
        ),
        "strong_red_ratio": round(
            float(strong_red_pixels.mean()),
            6,
        ),
        "saturated_ratio": round(
            float((saturation >= 70).mean()),
            6,
        ),
        "edge_density": round(
            float((edges > 0).mean()),
            6,
        ),
        "mean_saturation": round(
            float(np.mean(saturation)),
            3,
        ),
        "mean_value": round(
            float(np.mean(value)),
            3,
        ),
    }


def provisional_card_back(features):
    return bool(
        features["red_ratio"] >= 0.25
        and features["strong_red_ratio"] >= 0.12
        and features["saturated_ratio"] >= 0.45
    )


def latest_frame():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png"),
        key=lambda path: path.stat().st_mtime,
    )

    if not captures:
        raise SystemExit(
            "No window captures found"
        )

    return captures[-1]


def main():
    frame_path = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else latest_frame()
    )

    if not frame_path.exists():
        raise SystemExit(
            f"Frame not found: {frame_path}"
        )

    geometry = json.loads(
        GEOMETRY_PATH.read_text()
    )

    original = cv2.imread(
        str(frame_path)
    )

    if original is None or original.size == 0:
        raise SystemExit(
            f"Could not read frame: {frame_path}"
        )

    canonical = to_canonical_frame(
        original,
        geometry,
    )

    overlay = canonical.copy()
    results = {}
    detected_seats = []

    for seat in SEAT_ORDER:
        regions = (
            geometry
            .get("hole_cards", {})
            .get(seat, {})
        )

        card_results = {}

        for card_name in [
            "card_1",
            "card_2",
        ]:
            rect = regions.get(card_name)

            if not rect:
                continue

            card_crop = crop(
                canonical,
                rect,
            )

            features = card_back_features(
                card_crop,
            )

            detected = provisional_card_back(
                features
            )

            card_results[card_name] = {
                **features,
                "card_back": detected,
            }

            x = int(rect["x"])
            y = int(rect["y"])
            width = int(rect["width"])
            height = int(rect["height"])

            color = (
                (0, 255, 0)
                if detected
                else (0, 0, 255)
            )

            cv2.rectangle(
                overlay,
                (x, y),
                (x + width, y + height),
                color,
                2,
            )

            cv2.putText(
                overlay,
                (
                    f"{seat}:{card_name} "
                    f"red={features['red_ratio']:.2f}"
                ),
                (x, max(12, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.30,
                color,
                1,
                cv2.LINE_AA,
            )

        dealt_in = bool(
            card_results.get(
                "card_1",
                {},
            ).get("card_back")
            and card_results.get(
                "card_2",
                {},
            ).get("card_back")
        )

        if seat == "hero":
            # Hero has face-up cards, so Hero is established separately.
            dealt_in = True

        results[seat] = {
            "seat": seat,
            "dealt_in": dealt_in,
            "cards": card_results,
        }

        if dealt_in:
            detected_seats.append(
                seat
            )

    payload = {
        "frame": str(frame_path),
        "detected_seats": detected_seats,
        "detected_count": len(
            detected_seats
        ),
        "results": results,
    }

    OUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT_JSON.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n"
    )

    cv2.imwrite(
        str(OUT_OVERLAY),
        overlay,
    )

    print("frame:", frame_path)
    print(
        "detected_count:",
        len(detected_seats),
    )
    print(
        "detected_seats:",
        detected_seats,
    )
    print()

    for seat in SEAT_ORDER:
        result = results[seat]
        cards = result["cards"]

        first = cards.get(
            "card_1",
            {},
        )

        second = cards.get(
            "card_2",
            {},
        )

        print(
            f"{seat:20s} "
            f"dealt_in={str(result['dealt_in']):5s} "
            f"red=({first.get('red_ratio', 0.0):.3f},"
            f"{second.get('red_ratio', 0.0):.3f}) "
            f"strong=({first.get('strong_red_ratio', 0.0):.3f},"
            f"{second.get('strong_red_ratio', 0.0):.3f}) "
            f"sat=({first.get('saturated_ratio', 0.0):.3f},"
            f"{second.get('saturated_ratio', 0.0):.3f})"
        )

    print()
    print("json:", OUT_JSON)
    print("overlay:", OUT_OVERLAY)


if __name__ == "__main__":
    main()
