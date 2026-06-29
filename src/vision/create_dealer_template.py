from pathlib import Path
import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPTURE_DIR = PROJECT_ROOT / "runtime" / "window_captures"
TEMPLATE_DIR = PROJECT_ROOT / "assets" / "templates"

# Coordinates from clean ACR table crop:
# dealer button near Carlothedonkey / mike12123
X1, Y1, X2, Y2 = 1415, 730, 1490, 800


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    if not files:
        raise FileNotFoundError("No ACR table captures found.")
    return files[-1]


def main():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    image_path = latest_capture()
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"Could not read {image_path}")

    crop = img[Y1:Y2, X1:X2]
    out = TEMPLATE_DIR / "dealer_button.png"
    cv2.imwrite(str(out), crop)

    print(f"Source: {image_path}")
    print(f"Saved dealer template: {out}")
    print(f"Crop coords: x1={X1}, y1={Y1}, x2={X2}, y2={Y2}")


if __name__ == "__main__":
    main()
