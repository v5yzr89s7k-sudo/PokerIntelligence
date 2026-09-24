from pathlib import Path
import json
import re
import sys

import cv2
import pytesseract

ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = ROOT / "config/geometry.json"


def preprocess_variants(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    enlarged = cv2.resize(
        gray,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    blurred = cv2.GaussianBlur(
        enlarged,
        (3, 3),
        0,
    )

    contrast = cv2.convertScaleAbs(
        blurred,
        alpha=1.8,
        beta=8,
    )

    _, otsu = cv2.threshold(
        enlarged,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    return {
        "contrast": contrast,
        "otsu": otsu,
    }


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

    canonical_width = 934
    canonical_height = 696

    source_height, source_width = (
        img.shape[:2]
    )

    scale_x = (
        source_width
        / canonical_width
    )
    scale_y = (
        source_height
        / canonical_height
    )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    source_x1 = round(
        x * scale_x
    )
    source_y1 = round(
        y * scale_y
    )
    source_x2 = round(
        (x + w) * scale_x
    )
    source_y2 = round(
        (y + h) * scale_y
    )

    pad_x = round(
        20 * scale_x
    )
    pad_y = round(
        12 * scale_y
    )

    crops = {
        "current": img[
            source_y1:source_y2,
            source_x1:source_x2,
        ],
        "padded": img[
            max(
                0,
                source_y1 - pad_y,
            ):
            min(
                source_height,
                source_y2 + pad_y,
            ),
            max(
                0,
                source_x1 - pad_x,
            ):
            min(
                source_width,
                source_x2 + pad_x,
            ),
        ],
    }

    debug_dir = ROOT / "runtime" / "pot_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    reads = []
    candidates = []

    for crop_name, crop in crops.items():
        cv2.imwrite(
            str(debug_dir / f"pot_{crop_name}_crop.png"),
            crop,
        )

        for variant_name, processed in preprocess_variants(crop).items():
            cv2.imwrite(
                str(
                    debug_dir
                    / f"pot_{crop_name}_{variant_name}.png"
                ),
                processed,
            )

            for psm in (6, 7, 13):
                raw = pytesseract.image_to_string(
                    processed,
                    config=f"--psm {psm}",
                ).strip()

                value = parse_pot(raw)

                reads.append({
                    "crop": crop_name,
                    "variant": variant_name,
                    "psm": psm,
                    "raw": raw,
                    "pot_bb": value,
                })

                if (
                    value is not None
                    and 0.1 <= value <= 1000.0
                ):
                    candidates.append({
                        "value": round(float(value), 2),
                        "raw": raw,
                        "crop": crop_name,
                        "variant": variant_name,
                        "psm": psm,
                    })

    selected = None

    if candidates:
        support = {}

        for candidate in candidates:
            value = candidate["value"]
            support[value] = support.get(value, 0) + 1

        best_value = max(
            support,
            key=lambda value: (
                support[value],
                -candidates.index(
                    next(
                        item
                        for item in candidates
                        if item["value"] == value
                    )
                ),
            ),
        )

        selected = next(
            candidate
            for candidate in candidates
            if candidate["value"] == best_value
        )

        selected["support"] = support[best_value]

    if selected is None:
        raw_text = next(
            (
                read["raw"]
                for read in reads
                if read["raw"]
            ),
            "",
        )

        return {
            "ok": False,
            "pot_bb": None,
            "raw_text": raw_text,
            "reads": reads,
        }

    return {
        "ok": True,
        "pot_bb": selected["value"],
        "raw_text": selected["raw"],
        "read_mode": (
            f"{selected['crop']}:"
            f"{selected['variant']}:"
            f"psm{selected['psm']}"
        ),
        "support": selected["support"],
        "reads": reads,
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
