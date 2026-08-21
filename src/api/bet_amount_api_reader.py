from pathlib import Path
import base64
import cv2
import json
import os
import re

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


PROMPT = """
Read the poker bet amount shown in this small image crop.

Return RAW JSON ONLY:

{"bet_bb": number_or_null}

Rules:
- Read only the numeric bet amount.
- "BB" means big blinds and is not part of the number.
- Preserve decimals exactly.
- Do not infer an amount from chip appearance.
- If no clear bet amount is visible, return null.
- Do not return markdown.
""".strip()


def _extract_json(text):
    text = str(text or "").strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
        )
        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

    return json.loads(text)


def _encode_crop(frame_path, seat):
    image = cv2.imread(str(frame_path))

    if image is None:
        raise RuntimeError(
            f"could not read frame: {frame_path}"
        )

    image = cv2.resize(
        image,
        (934, 696),
        interpolation=cv2.INTER_AREA,
    )

    region = (
        GEOMETRY
        .get("bet_regions", {})
        .get(seat)
    )

    if not region:
        raise RuntimeError(
            f"missing bet region for seat={seat}"
        )

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    # Preserve the complete amount plaque with modest padding.
    px = 8
    py = 6

    x0 = max(0, x - px)
    y0 = max(0, y - py)
    x1 = min(image.shape[1], x + w + px)
    y1 = min(image.shape[0], y + h + py)

    crop = image[y0:y1, x0:x1]

    ok, encoded = cv2.imencode(
        ".jpg",
        crop,
        [int(cv2.IMWRITE_JPEG_QUALITY), 92],
    )

    if not ok:
        raise RuntimeError(
            "bet crop JPEG encoding failed"
        )

    payload = base64.b64encode(
        encoded.tobytes()
    ).decode("ascii")

    return (
        "data:image/jpeg;base64,"
        + payload
    )


def read_bet_amount(frame_path, seat):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set"
        )

    client = OpenAI(timeout=20.0)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": PROMPT,
                },
                {
                    "type": "input_image",
                    "image_url": _encode_crop(
                        frame_path,
                        seat,
                    ),
                },
            ],
        }],
    )

    raw = response.output_text.strip()
    data = _extract_json(raw)

    value = data.get("bet_bb")

    if value is None:
        return {
            "bet_bb": None,
            "raw_text": raw,
        }

    value = float(value)

    if not 0.0 < value <= 1000.0:
        raise ValueError(
            f"bet amount out of range: {value}"
        )

    return {
        "bet_bb": round(value, 2),
        "raw_text": raw,
    }
