from pathlib import Path
from time import perf_counter
import base64
import json
import os

import cv2
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]

# Created once when api_board_worker starts and reused for all streets.
CLIENT = OpenAI(timeout=45.0)

PROMPT_BOTH = """
Read ONLY the board/community cards from this ACR screenshot.

The first image is the complete table.
The second image is an enlarged crop of the board area.
Use both images together. The complete table helps verify cards near
the crop boundaries.

Return RAW JSON ONLY:
{"board":[],"street":"","confidence":0.0}

Use ASCII card notation only: Ah, Ad, Ac, As, Td, 7s.
Board must contain 0, 3, 4, or 5 cards.
Preserve left-to-right card order.
Use [] if no board cards are visible.
Do not guess.
"""

PROMPT_CROP = """
Read ONLY the board/community cards from this enlarged ACR board crop.

Return RAW JSON ONLY:
{"board":[],"street":"","confidence":0.0}

Use ASCII card notation only: Ah, Ad, Ac, As, Td, 7s.
Board must contain 0, 3, 4, or 5 cards.
Preserve left-to-right card order.
Use [] if no board cards are visible.
Do not guess.
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
        raise RuntimeError("OpenCV could not encode board JPEG")

    return encoded.tobytes()


def _prepare_images(frame):
    image = cv2.imread(str(frame))

    if image is None:
        raise RuntimeError(f"could not read board frame: {frame}")

    image = cv2.resize(image, (934, 696))

    # Preserve the currently validated crop exactly.
    board = image[245:360, 300:640]

    if board.size == 0:
        raise RuntimeError("board crop is empty")

    board = cv2.resize(
        board,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC,
    )

    return image, board


def _extract_json(text):
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            f"board response contained no JSON object: {cleaned!r}"
        )

    return json.loads(cleaned[start:end + 1])


def read_board(frame, image_mode=None):
    total_t0 = perf_counter()

    frame = Path(frame).expanduser().resolve()

    if not frame.exists():
        raise FileNotFoundError(frame)

    mode = (
        image_mode
        or os.environ.get("BOARD_IMAGE_MODE", "both")
    ).strip().lower()

    if mode not in ("both", "crop"):
        raise ValueError(
            f"unsupported BOARD_IMAGE_MODE={mode!r}; "
            "expected 'both' or 'crop'"
        )

    prepare_t0 = perf_counter()
    table_image, board_image = _prepare_images(frame)
    prepare_ms = (perf_counter() - prepare_t0) * 1000.0

    encode_t0 = perf_counter()
    board_url = _data_url(_encode_jpeg(board_image, 90))

    if mode == "both":
        table_url = _data_url(_encode_jpeg(table_image, 65))
        content = [
            {"type": "input_text", "text": PROMPT_BOTH},
            {"type": "input_image", "image_url": table_url},
            {"type": "input_image", "image_url": board_url},
        ]
    else:
        content = [
            {"type": "input_text", "text": PROMPT_CROP},
            {"type": "input_image", "image_url": board_url},
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

    board = data.get("board") or []

    result = {
        "board": board,
        "street": data.get("street") or "",
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
