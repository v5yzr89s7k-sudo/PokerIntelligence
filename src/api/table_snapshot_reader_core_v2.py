from pathlib import Path
from time import perf_counter
import base64
import json

import cv2
from openai import OpenAI

from src.api.canonical_frame import to_canonical_frame
from src.api.seat_crop_builder import (
    build_seat_cards,
    load_geometry,
)
from src.events.detectors.seat_occupancy_detector import (
    SEAT_ORDER,
)
from src.vision.dealer_detector import detect_dealer_button


ROOT = Path(__file__).resolve().parents[2]
GEOMETRY = load_geometry()

# Initialized once per worker process.
CLIENT = OpenAI(timeout=45.0)

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
    "MUCK",
    "SHOW",
}

PROMPT_HEADER = """
Read this ACR poker table using the deterministic seat information supplied below.

Return RAW JSON ONLY:

{
  "readings": [
    {
      "seat": "",
      "name": "",
      "stack_text": "",
      "stack_bb": null
    }
  ],
  "confidence": 0.0
}

Rules:

- Every image is one immutable physical-seat crop.
- The text immediately before each crop gives its authoritative seat label.
- Never change, infer, compress, rotate, or shift a supplied seat label.
- Read only the player name and visible stack from each supplied seat crop.
- Do not decide whether a seat is occupied. Local vision already determined that.
- Return exactly one reading for every supplied occupied seat.
- Hero is the physical bottom-center seat labeled hero.
- A folded player still occupies the seat.
- Ignore transient action text such as CHECK, FOLD, CALL, BET, RAISE,
  ALL IN, POST SB, POST BB, ANTE, MUCK, and SHOW.
- Never use transient action text as a player name.
- stack_text must preserve the visible text.
- stack_bb must be numeric only when clearly shown in big blinds.
- Use "" or null when text cannot be read confidently.
- Do not read board cards.
- Do not read hole cards.
- Do not infer hidden information.
"""


def _encode_jpeg(image, quality=88):
    ok, encoded = cv2.imencode(
        ".jpg",
        image,
        [
            int(cv2.IMWRITE_JPEG_QUALITY),
            int(quality),
        ],
    )

    if not ok:
        raise RuntimeError(
            "could not encode Snapshot V2 JPEG"
        )

    return encoded.tobytes()


def _data_url(raw):
    encoded = base64.b64encode(raw).decode(
        "utf-8"
    )
    return (
        "data:image/jpeg;base64,"
        + encoded
    )


def _extract_json(text):
    cleaned = str(text or "").strip()

    if cleaned.startswith("```"):
        cleaned = (
            cleaned
            .split("```json")[-1]
            .split("```")[0]
            .strip()
        )

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end < start:
        raise ValueError(
            "Snapshot V2 response contained no JSON: "
            f"{cleaned!r}"
        )

    return json.loads(
        cleaned[start:end + 1]
    )


def _normalize_stack_bb(value):
    if isinstance(value, str):
        cleaned = (
            value.strip()
            .lower()
            .replace("bb", "")
            .replace(",", "")
        )

        try:
            value = float(cleaned)
        except ValueError:
            return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def _normalize_name(value):
    name = str(value or "").strip()
    key = " ".join(
        name.upper().split()
    )

    if key in INVALID_PLAYER_NAMES:
        return ""

    return name


def _prepare(frame_path):
    image = cv2.imread(
        str(frame_path)
    )

    if image is None or image.size == 0:
        raise RuntimeError(
            f"could not read snapshot frame: "
            f"{frame_path}"
        )

    canonical = to_canonical_frame(
        image,
        GEOMETRY,
    )

    # Build all physical-seat cards so Hero remains available even if
    # detector behavior changes in an unusual visual state.
    all_cards = build_seat_cards(
        canonical,
        geometry=GEOMETRY,
        occupied_only=False,
    )

    selected_cards = [
        card
        for card in all_cards
        if card["occupied"]
        or card["seat"] == "hero"
    ]

    if not selected_cards:
        raise RuntimeError(
            "Snapshot V2 found no occupied seats"
        )

    return canonical, selected_cards


def _build_content(cards):
    occupied_labels = [
        card["seat"]
        for card in cards
    ]

    prompt = (
        PROMPT_HEADER
        + "\nAuthoritative occupied seats:\n"
        + json.dumps(
            occupied_labels
        )
    )

    content = [
        {
            "type": "input_text",
            "text": prompt,
        },
    ]

    image_bytes = 0

    for card in cards:
        seat = card["seat"]

        content.append({
            "type": "input_text",
            "text": (
                "AUTHORITATIVE PHYSICAL SEAT: "
                f"{seat}"
            ),
        })

        crop = card["image"]

        # Enlarge small text without changing its physical seat identity.
        crop = cv2.resize(
            crop,
            None,
            fx=2.0,
            fy=2.0,
            interpolation=cv2.INTER_CUBIC,
        )

        raw = _encode_jpeg(
            crop,
            quality=90,
        )

        image_bytes += len(raw)

        content.append({
            "type": "input_image",
            "image_url": _data_url(raw),
        })

    return content, image_bytes


def _normalize_result(data, cards, dealer):
    allowed = {
        card["seat"]
        for card in cards
    }

    readings_by_seat = {}

    for raw in data.get("readings") or []:
        if not isinstance(raw, dict):
            continue

        seat = str(
            raw.get("seat") or ""
        ).strip()

        if (
            seat not in allowed
            or seat in readings_by_seat
        ):
            continue

        readings_by_seat[seat] = {
            "seat": seat,
            "name": _normalize_name(
                raw.get("name")
            ),
            "stack_text": str(
                raw.get("stack_text") or ""
            ).strip(),
            "stack_bb": _normalize_stack_bb(
                raw.get("stack_bb")
            ),
            "is_hero": seat == "hero",
            "is_active": True,
        }

    # Deterministic topology owns the player list. GPT may leave OCR fields
    # blank, but it cannot delete or invent an occupied physical seat.
    players = []

    for card in cards:
        seat = card["seat"]

        player = readings_by_seat.get(
            seat,
            {
                "seat": seat,
                "name": "",
                "stack_text": "",
                "stack_bb": None,
                "is_hero": seat == "hero",
                "is_active": True,
            },
        )

        player["occupancy_confidence"] = float(
            card["occupancy_confidence"]
        )

        players.append(player)

    if dealer not in SEAT_ORDER:
        dealer = ""

    return {
        "dealer_button_seat": dealer,
        "players": players,
        "occupied_seats": [
            card["seat"]
            for card in cards
        ],
        "confidence": data.get(
            "confidence"
        ),
        "source": "snapshot_v2",
    }


def read_table_snapshot_v2(frame):
    total_t0 = perf_counter()

    frame_path = Path(
        frame
    ).expanduser().resolve()

    if not frame_path.exists():
        raise FileNotFoundError(
            frame_path
        )

    prepare_t0 = perf_counter()
    canonical, cards = _prepare(
        frame_path
    )
    prepare_ms = (
        perf_counter() - prepare_t0
    ) * 1000.0

    dealer_t0 = perf_counter()
    dealer_result = detect_dealer_button(
        canonical
    )
    dealer = (
        dealer_result["dealer_button_seat"]
        if dealer_result["found"]
        else ""
    )
    dealer_ms = (
        perf_counter() - dealer_t0
    ) * 1000.0

    payload_t0 = perf_counter()
    content, image_bytes = _build_content(
        cards,
    )
    payload_ms = (
        perf_counter() - payload_t0
    ) * 1000.0

    api_t0 = perf_counter()
    response = CLIENT.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": content,
        }],
    )
    api_ms = (
        perf_counter() - api_t0
    ) * 1000.0

    parse_t0 = perf_counter()
    data = _extract_json(
        response.output_text
    )
    result = _normalize_result(
        data,
        cards,
        dealer,
    )
    parse_ms = (
        perf_counter() - parse_t0
    ) * 1000.0

    timings = {
        "prepare_ms": prepare_ms,
        "dealer_ms": dealer_ms,
        "payload_ms": payload_ms,
        "api_ms": api_ms,
        "parse_ms": parse_ms,
        "total_ms": (
            perf_counter() - total_t0
        ) * 1000.0,
        "image_count": len(cards),
        "seat_card_count": len(cards),
        "image_bytes": image_bytes,
    }

    return result, timings
