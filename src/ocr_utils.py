import json
import re
from pathlib import Path
from typing import Dict, Tuple, Any

from PIL import Image, ImageOps, ImageEnhance
import pytesseract

Box = Tuple[int, int, int, int]


def load_config(project_root: Path) -> Dict[str, Any]:
    with open(project_root / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def rel_to_abs_box(image: Image.Image, rel_box) -> Box:
    w, h = image.size
    x, y, rw, rh = rel_box
    return (int(x * w), int(y * h), int((x + rw) * w), int((y + rh) * h))


def preprocess_for_ocr(img: Image.Image, scale: int = 2) -> Image.Image:
    img = img.convert("RGB")
    img = ImageOps.grayscale(img)
    img = ImageEnhance.Contrast(img).enhance(2.2)
    img = ImageEnhance.Sharpness(img).enhance(1.8)
    if scale and scale != 1:
        img = img.resize((img.width * scale, img.height * scale))
    return img


def crop_regions(image_path: Path, config: Dict[str, Any], debug_dir: Path) -> Dict[str, Image.Image]:
    debug_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path)
    regions = {}
    for name, rel_box in config.get("regions_relative", {}).items():
        box = rel_to_abs_box(image, rel_box)
        crop = image.crop(box)
        regions[name] = crop
        crop.save(debug_dir / f"{name}.png")
        preprocess_for_ocr(crop).save(debug_dir / f"{name}_ocr.png")
    return regions


def ocr_image(img: Image.Image, config: Dict[str, Any], psm: int = 6) -> str:
    pre = preprocess_for_ocr(img)
    tess_config = f"--psm {psm}"
    text = pytesseract.image_to_string(pre, lang=config.get("ocr_lang", "eng"), config=tess_config)
    return text.strip()


def ocr_regions(image_path: Path, config: Dict[str, Any], debug_dir: Path) -> Dict[str, str]:
    crops = crop_regions(image_path, config, debug_dir)
    output = {}
    for name, img in crops.items():
        psm = 7 if name in {"hero_cards", "hero_stack", "pot_area"} else 6
        output[name] = ocr_image(img, config, psm=psm)
    return output


def extract_first_bb(text: str):
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*BB", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def detect_break_state(region_ocr: Dict[str, str]) -> bool:
    haystack = "\n".join(region_ocr.values()).lower()
    return "resume gameplay" in haystack or "will resume" in haystack or "break" in haystack


def parse_blinds_antes(header_text: str):
    # Example: No Limit - 800 / 1,600, Ante 200
    clean = header_text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?:\s*,?\s*Ante\s*(\d+(?:\.\d+)?))?", clean, re.I)
    if not m:
        return None
    sb = float(m.group(1))
    bb = float(m.group(2))
    ante = float(m.group(3)) if m.group(3) else None
    return {"small_blind": sb, "big_blind": bb, "ante": ante}


def parse_players_left(header_text: str):
    # Example: Your Position | 14 of 26
    m = re.search(r"(\d+)\s+of\s+(\d+)", header_text, re.I)
    if not m:
        return None
    return {"hero_rank": int(m.group(1)), "players_left": int(m.group(2))}


def parse_pot_bb(pot_text: str):
    if not pot_text:
        return None
    text = pot_text.replace(",", "")
    m = re.search(r"(?:Total\s*:?)?\s*(\d+(?:\.\d+)?)\s*BB", text, re.I)
    if m:
        return float(m.group(1))
    return None
