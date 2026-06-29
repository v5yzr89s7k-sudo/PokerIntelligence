from pathlib import Path
import cv2

from dealer_detector import DEALER_SEARCH_ZONES, latest_acr_capture, crop_pct


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT = PROJECT_ROOT / "runtime" / "debug_crops" / "dealer_search_overlay.png"


def main():
    image = latest_acr_capture()
    img = cv2.imread(str(image))
    if img is None:
        raise FileNotFoundError(image)

    for seat_name, zone in DEALER_SEARCH_ZONES.items():
        _, (x1, y1, x2, y2) = crop_pct(img, zone)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, seat_name, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), img)

    print(f"Input: {image}")
    print(f"Overlay written: {OUT}")


if __name__ == "__main__":
    main()
