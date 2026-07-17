from pathlib import Path
from time import perf_counter
import base64
import json
import os

import cv2
import numpy as np
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = json.loads(
    (ROOT / "config/geometry.json").read_text()
)

SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]

# Initialized once when the snapshot worker starts.
CLIENT = OpenAI(timeout=45.0)

PROMPT = """
Read ONLY the current table snapshot from this ACR poker screenshot.

Return RAW JSON ONLY:
{
  "dealer_button_seat":"",
  "players":[
    {
      "seat":"",
      "name":"",
      "stack_text":"",
      "stack_bb":null,
      "is_hero":false,
      "is_active":true
    }
  ],
  "confidence":0.0
}

Rules:
- Hero is always the bottom-center player only.
- Do NOT label the bottom-left player as hero.
- The hero seat is directly above the Fold/Call/Raise buttons.
- Identify occupied seats only.
- The second image is a labeled seat montage.
- Every montage panel has the authoritative physical seat label written above it.
- Never shift or compress players across an empty seat.
- Return a player only under the exact label printed above that player's panel.
- If a labeled panel is empty, do not return a player for that seat.
- Words such as CHECK, FOLD, CALL, BET, RAISE, ALL IN, POST SB, POST BB,
  and ANTE are transient poker-action overlays.
- Never treat an action overlay as a player name.
- Never determine occupancy from an action overlay alone.
- Determine occupancy from the visible avatar/nameplate/stack structure.
- A folded player may still occupy the seat; return that player when the
  avatar, stack, or underlying nameplate shows the seat is occupied.
- Use seat labels exactly:
  seat_top,
  seat_upper_right,
  seat_mid_right,
  seat_lower_right,
  hero,
  seat_lower_left,
  seat_mid_left,
  seat_upper_left
- dealer_button_seat must use the same labels or "".
- stack_text must preserve visible text.
- stack_bb must be numeric only when clear, otherwise null.
- Do not read board cards.
- Do not read hero cards.
- Do not infer hidden information.
- Use "" or null when uncertain.
"""


def _encode_jpeg(image, quality):
    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)],
    )

    if not ok:
        raise RuntimeError("could not encode snapshot JPEG")

    return encoded.tobytes()


def _data_url(raw):
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _extract_json(text):
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            f"snapshot response contained no JSON: {cleaned!r}"
        )

    return json.loads(cleaned[start:end + 1])


def _seat_crop_bounds(seat):
    """
    Snapshot reader crop.

    Focus almost entirely on the information required for seat
    assignment:

        avatar
        nameplate
        stack

    Hero cards and opponent cards intentionally remain outside the crop.
    """

    seat_rect = GEOMETRY["seat_regions"][seat]
    stack_rect = GEOMETRY["stack_regions"][seat]

    x1 = min(
        seat_rect["x"],
        stack_rect["x"],
    )

    y1 = seat_rect["y"] - 55

    x2 = max(
        seat_rect["x"] + seat_rect["width"],
        stack_rect["x"] + stack_rect["width"],
    )

    y2 = stack_rect["y"] + stack_rect["height"]

    x_margin = 18
    y_margin = 8

    return (
        max(0, int(x1 - x_margin)),
        max(0, int(y1 - y_margin)),
        min(934, int(x2 + x_margin)),
        min(696, int(y2 + y_margin)),
    )


def _build_seat_montage(image):
    """
    Return a two-column labeled montage containing all eight physical seats.

    The label is rendered into the image itself so the vision model cannot
    compress players across empty seats or reinterpret the seat order.
    """
    panels = []

    for seat in SEAT_ORDER:
        x1, y1, x2, y2 = _seat_crop_bounds(seat)
        crop = image[y1:y2, x1:x2]

        if crop.size == 0:
            raise RuntimeError(
                f"empty snapshot crop for {seat}"
            )

        crop = cv2.resize(
            crop,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC,
        )

        label_height = 42
        panel_width = max(crop.shape[1], 390)

        panel = np.zeros(
            (
                label_height + crop.shape[0],
                panel_width,
                3,
            ),
            dtype=np.uint8,
        )

        panel[
            label_height:label_height + crop.shape[0],
            0:crop.shape[1],
        ] = crop

        cv2.putText(
            panel,
            seat,
            (8, 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        panels.append(panel)

    row_width = max(
        panels[index].shape[1]
        + panels[index + 1].shape[1]
        for index in range(0, len(panels), 2)
    )

    rows = []

    for index in range(0, len(panels), 2):
        left = panels[index]
        right = panels[index + 1]

        row_height = max(
            left.shape[0],
            right.shape[0],
        )

        normalized = []

        for panel in (left, right):
            if panel.shape[0] < row_height:
                vertical_pad = np.zeros(
                    (
                        row_height - panel.shape[0],
                        panel.shape[1],
                        3,
                    ),
                    dtype=np.uint8,
                )
                panel = np.vstack([
                    panel,
                    vertical_pad,
                ])

            normalized.append(panel)

        row = np.hstack(normalized)

        if row.shape[1] < row_width:
            horizontal_pad = np.zeros(
                (
                    row.shape[0],
                    row_width - row.shape[1],
                    3,
                ),
                dtype=np.uint8,
            )
            row = np.hstack([
                row,
                horizontal_pad,
            ])

        rows.append(row)

    return np.vstack(rows)


def _prepare(frame, mode):
    image = cv2.imread(str(frame))

    if image is None:
        raise RuntimeError(f"could not read snapshot frame: {frame}")

    image = cv2.resize(image, (934, 696))

    full_quality = 70
    full_bytes = _encode_jpeg(image, full_quality)

    crop_bytes = None

    if mode == "current":
        montage = _build_seat_montage(image)
        crop_bytes = _encode_jpeg(
            montage,
            88,
        )

    elif mode == "compact":
        montage = _build_seat_montage(image)
        montage = cv2.resize(
            montage,
            None,
            fx=0.72,
            fy=0.72,
            interpolation=cv2.INTER_AREA,
        )
        crop_bytes = _encode_jpeg(
            montage,
            78,
        )

    elif mode != "full":
        raise ValueError(
            f"unsupported SNAPSHOT_IMAGE_MODE={mode!r}; "
            "expected current, compact, or full"
        )

    return full_bytes, crop_bytes


INVALID_PLAYER_NAMES = {
    "CALL",
    "CALL ANY",
    "CHECK",
    "CHECK/FOLD",
    "FOLD",
    "RAISE",
    "BET",
    "ALL IN",
    "ALL-IN",
    "POST SB",
    "POST BB",
    "ANTE",
    "SITTING OUT",
    "SIT OUT",
    "SITTING OUT",
    "MUCK",
    "SHOW",
}


def _normalize_player(player):
    normalized = dict(player)

    name = str(normalized.get("name") or "").strip()
    name_key = " ".join(name.upper().split())

    if name_key in INVALID_PLAYER_NAMES:
        normalized["name"] = ""
    else:
        normalized["name"] = name

    stack_text = str(normalized.get("stack_text") or "").strip()
    normalized["stack_text"] = stack_text

    stack_bb = normalized.get("stack_bb")

    if isinstance(stack_bb, str):
        try:
            stack_bb = float(stack_bb)
        except ValueError:
            stack_bb = None

    if isinstance(stack_bb, (int, float)):
        normalized["stack_bb"] = stack_bb
    else:
        normalized["stack_bb"] = None

    normalized["is_hero"] = normalized.get("seat") == "hero"
    normalized["is_active"] = bool(
        normalized.get("is_active", True)
    )

    return normalized


def _normalize_snapshot(data):
    allowed_seats = {
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
    }

    players = []
    seen_seats = set()

    for raw_player in data.get("players") or []:
        if not isinstance(raw_player, dict):
            continue

        player = _normalize_player(raw_player)
        seat = player.get("seat")

        if seat not in allowed_seats:
            continue

        if seat in seen_seats:
            continue

        seen_seats.add(seat)
        players.append(player)

    dealer = data.get("dealer_button_seat") or ""

    if dealer not in allowed_seats:
        dealer = ""

    return {
        "dealer_button_seat": dealer,
        "players": players,
        "confidence": data.get("confidence"),
    }


def read_table_snapshot(frame, image_mode=None):
    total_t0 = perf_counter()

    frame = Path(frame).expanduser().resolve()

    if not frame.exists():
        raise FileNotFoundError(frame)

    mode = (
        image_mode
        or os.environ.get("SNAPSHOT_IMAGE_MODE", "current")
    ).strip().lower()

    prepare_t0 = perf_counter()
    full_bytes, crop_bytes = _prepare(frame, mode)
    prepare_ms = (perf_counter() - prepare_t0) * 1000.0

    encode_t0 = perf_counter()

    content = [
        {"type": "input_text", "text": PROMPT},
        {
            "type": "input_image",
            "image_url": _data_url(full_bytes),
        },
    ]

    if crop_bytes is not None:
        content.append({
            "type": "input_image",
            "image_url": _data_url(crop_bytes),
        })

    payload_ms = (perf_counter() - encode_t0) * 1000.0

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

    result = _normalize_snapshot(data)

    timings = {
        "image_mode": mode,
        "image_count": 1 + int(crop_bytes is not None),
        "full_bytes": len(full_bytes),
        "crop_bytes": len(crop_bytes) if crop_bytes is not None else 0,
        "prepare_ms": prepare_ms,
        "payload_ms": payload_ms,
        "api_ms": api_ms,
        "parse_ms": parse_ms,
        "total_ms": (perf_counter() - total_t0) * 1000.0,
    }

    return result, timings
