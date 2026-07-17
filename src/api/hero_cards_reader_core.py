from pathlib import Path
from time import perf_counter
import base64
import json
import os

import cv2
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY_PATH = ROOT / "config/geometry.json"

# Created once when api_hero_worker starts, then reused for every hand.
CLIENT = OpenAI(timeout=45.0)

PROMPT_CROP = """
Read ONLY the two hero hole cards from this enlarged ACR hero-card crop.

Return RAW JSON ONLY:
{"hero_cards":["",""],"confidence":0.0}

Use ASCII card notation only: Ah, Ad, Ac, As, Td, 7s.
Read each rank and suit separately.
Carefully distinguish hearts from diamonds.
Carefully distinguish clubs from spades.
Do not guess. Use "" for a card if uncertain.
"""

PROMPT_BOTH = """
Read ONLY the hero hole cards from this ACR screenshot.

Hero ALWAYS sits bottom center.
The second image is an enlarged crop containing only the two hero cards.
Use the enlarged crop to verify ranks and suits.

Return RAW JSON ONLY:
{"hero_cards":["",""],"confidence":0.0}

Use ASCII card notation only: Ah, Ad, Ac, As, Td, 7s.
Read each rank and suit separately.
Carefully distinguish hearts from diamonds.
Carefully distinguish clubs from spades.
Do not guess. Use "" for a card if uncertain.
"""


def _data_url(raw):
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _encode_jpeg(image, quality):
    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )

    if not ok:
        raise RuntimeError("OpenCV could not encode JPEG")

    return encoded.tobytes()


def _prepare_images(frame):
    image = cv2.imread(str(frame))

    if image is None:
        raise RuntimeError(f"could not read Hero frame: {frame}")

    image = cv2.resize(image, (934, 696))

    with GEOMETRY_PATH.open() as f:
        geometry = json.load(f)

    hero_cards = (
        geometry.get("hero_cards")
        or geometry.get("hole_cards", {}).get("hero", {})
    )

    if not hero_cards:
        raise RuntimeError("Hero-card geometry is missing")

    xs = [region["x"] for region in hero_cards.values()]
    ys = [region["y"] for region in hero_cards.values()]
    x2s = [
        region["x"] + region["width"]
        for region in hero_cards.values()
    ]
    y2s = [
        region["y"] + region["height"]
        for region in hero_cards.values()
    ]

    pad = 12

    x1 = max(0, int(min(xs) - pad))
    y1 = max(0, int(min(ys) - pad))
    x2 = min(image.shape[1], int(max(x2s) + pad))
    y2 = min(image.shape[0], int(max(y2s) + pad))

    hero = image[y1:y2, x1:x2]

    if hero.size == 0:
        raise RuntimeError("Hero-card crop is empty")

    hero = cv2.resize(
        hero,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    return image, hero


def _extract_json(text):
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end < start:
        raise ValueError(f"Hero response contained no JSON object: {cleaned!r}")

    return json.loads(cleaned[start:end + 1])


def read_hero_cards(frame, image_mode=None):
    total_t0 = perf_counter()

    frame = Path(frame).expanduser().resolve()

    if not frame.exists():
        raise FileNotFoundError(frame)

    mode = (
        image_mode
        or os.environ.get("HERO_IMAGE_MODE", "crop")
    ).strip().lower()

    if mode not in ("crop", "both"):
        raise ValueError(
            f"unsupported HERO_IMAGE_MODE={mode!r}; "
            "expected 'crop' or 'both'"
        )

    prepare_t0 = perf_counter()
    table_image, hero_image = _prepare_images(frame)
    prepare_ms = (perf_counter() - prepare_t0) * 1000.0

    encode_t0 = perf_counter()
    hero_url = _data_url(_encode_jpeg(hero_image, 90))

    if mode == "both":
        table_url = _data_url(_encode_jpeg(table_image, 65))
        prompt = PROMPT_BOTH
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": table_url},
            {"type": "input_image", "image_url": hero_url},
        ]
    else:
        prompt = PROMPT_CROP
        content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": hero_url},
        ]

    encode_ms = (perf_counter() - encode_t0) * 1000.0

    api_t0 = perf_counter()
    response = CLIENT.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": content,
        }],
    )
    api_ms = (perf_counter() - api_t0) * 1000.0

    parse_t0 = perf_counter()
    data = _extract_json(response.output_text)
    parse_ms = (perf_counter() - parse_t0) * 1000.0

    cards = data.get("hero_cards") or []

    result = {
        "hero_cards": cards,
        "confidence": data.get("confidence"),
    }

    timings = {
        "image_mode": mode,
        "prepare_ms": prepare_ms,
        "encode_ms": encode_ms,
        "api_ms": api_ms,
        "parse_ms": parse_ms,
        "total_ms": (perf_counter() - total_t0) * 1000.0,
    }

    return result, timings
