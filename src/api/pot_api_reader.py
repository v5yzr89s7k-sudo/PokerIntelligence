from pathlib import Path
import json
import re
import sys

import cv2
import pytesseract

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = ROOT / "config/geometry.json"


def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Preserve anti-aliased white text instead of hard-thresholding it.
    gray = cv2.resize(
        gray,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    gray = cv2.convertScaleAbs(
        gray,
        alpha=1.8,
        beta=8,
    )

    return gray


def parse_pot(text):
    if not text:
        return None

    text = text.replace(",", "")

    # OCR occasionally confuses lowercase l with uppercase I.
    text = text.replace("TotaI", "Total")

    m = re.search(
        r"(?:Total\s*:?)?\s*(\d+(?:\.\d+)?)\s*BB",
        text,
        re.IGNORECASE,
    )

    if not m:
        return None

    return float(m.group(1))


def read_pot(frame):
    frame = Path(frame)

    geometry = json.loads(GEOMETRY.read_text())
    region = geometry["pot_region"]["main_pot"]

    img = cv2.imread(str(frame))
    if img is None:
        return {
            "ok": False,
            "pot_bb": None,
            "raw_text": "",
            "error": "could_not_read_image",
        }

    img = cv2.resize(
        img,
        (934, 696),
        interpolation=cv2.INTER_AREA,
    )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[y:y+h, x:x+w]
    processed = preprocess(crop)

    debug_dir = ROOT / "runtime" / "pot_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(debug_dir / "pot_crop.png"), crop)
    cv2.imwrite(str(debug_dir / "pot_processed.png"), processed)

    raw = pytesseract.image_to_string(
        processed,
        config="--psm 7",
    ).strip()

    pot = parse_pot(raw)

    if pot is not None and not 0.1 <= pot <= 1000.0:
        pot = None

    return {
        "ok": pot is not None,
        "pot_bb": pot,
        "raw_text": raw,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: pot_api_reader.py <frame>")

    print(json.dumps(
        read_pot(Path(sys.argv[1])),
        indent=2,
    ))


if __name__ == "__main__":
    main()
