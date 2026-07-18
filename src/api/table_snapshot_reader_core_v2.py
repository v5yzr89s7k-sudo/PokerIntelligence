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
from src.vision.stack_reader import read_stack
from src.api.snapshot_cache import (
    load_cache,
    save_cache,
    lookup as cache_lookup,
    update as cache_update,
    stack_lookup,
    stack_update,
)


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


def _cache_fingerprint_image(card):
    seat = card["seat"]
    seat_rect = GEOMETRY["seat_regions"][seat]
    bounds = card["bounds"]

    x1 = int(seat_rect["x"]) - bounds["x1"]
    y1 = int(seat_rect["y"]) - bounds["y1"]
    x2 = x1 + int(seat_rect["width"])
    y2 = y1 + int(seat_rect["height"])

    return card["image"][y1:y2, x1:x2]


def _cache_player(entry, card):
    return {
        "seat": card["seat"],
        "name": _normalize_name(entry.get("name")),
        "stack_text": str(entry.get("stack_text") or "").strip(),
        "stack_bb": _normalize_stack_bb(entry.get("stack_bb")),
        "is_hero": card["seat"] == "hero",
        "is_active": True,
        "occupancy_confidence": float(card["occupancy_confidence"]),
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

    cache = load_cache()
    cached_players = {}
    changed_cards = []

    for card in cards:
        entry = cache_lookup(
            cache,
            card["seat"],
            _cache_fingerprint_image(card),
        )

        if entry is None:
            changed_cards.append(card)
        else:
            cached_players[card["seat"]] = (
                _cache_player(entry, card)
            )

    payload_t0 = perf_counter()

    if changed_cards:
        content, image_bytes = _build_content(
            changed_cards,
        )
    else:
        content = None
        image_bytes = 0

    payload_ms = (
        perf_counter() - payload_t0
    ) * 1000.0

    api_ms = 0.0
    parse_ms = 0.0
    confidence = None
    fresh_players = {}

    if changed_cards:
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
        partial = _normalize_result(
            data,
            changed_cards,
            dealer,
        )
        confidence = partial.get(
            "confidence"
        )
        fresh_players = {
            player["seat"]: player
            for player in partial["players"]
        }

        for card in changed_cards:
            player = fresh_players[
                card["seat"]
            ]
            cache_update(
                cache,
                card["seat"],
                _cache_fingerprint_image(card),
                {
                    "name": player["name"],
                    "stack_text": player["stack_text"],
                    "stack_bb": player["stack_bb"],
                },
            )

        save_cache(cache)
        parse_ms = (
            perf_counter() - parse_t0
        ) * 1000.0

    players = []

    stack_t0 = perf_counter()
    stack_readings = {}

    for card in cards:
        seat = card["seat"]
        region = GEOMETRY["stack_regions"][seat]

        x1 = int(region["x"]) - card["bounds"]["x1"]
        y1 = int(region["y"]) - card["bounds"]["y1"]
        x2 = x1 + int(region["width"])
        y2 = y1 + int(region["height"])

        stack_crop = card["image"][y1:y2, x1:x2]

        cached_stack = stack_lookup(
            cache,
            seat,
            stack_crop,
        )

        if (
            cached_stack
            and cached_stack.get("stack_bb") is not None
        ):
            stack_readings[seat] = {
                "stack_bb": cached_stack["stack_bb"],
                "stack_text": cached_stack["stack_text"],
                "confidence": float(
                    cached_stack.get("confidence")
                    or 0.0
                ),
                "votes": int(
                    cached_stack.get("votes")
                    or 0
                ),
                "mode": cached_stack.get(
                    "mode",
                    "cache",
                ),
                "source": "cache",
            }
            continue

        result = read_stack(stack_crop)

        trusted_stack = (
            result.get("stack_bb") is not None
            and float(result.get("stack_bb")) > 0.0
            and float(result.get("confidence") or 0.0) >= 0.95
            and int(result.get("votes") or 0) >= 2
        )

        if trusted_stack:
            stack_readings[seat] = result

            stack_update(
                cache,
                seat,
                stack_crop,
                {
                    "stack_bb": result["stack_bb"],
                    "stack_text": result["stack_text"],
                    "confidence": result["confidence"],
                    "votes": result["votes"],
                    "mode": result["mode"],
                },
            )
        else:
            stack_readings[seat] = {
                **result,
                "stack_bb": None,
                "stack_text": "",
            }

    save_cache(cache)

    stack_ms = (
        perf_counter() - stack_t0
    ) * 1000.0

    for card in cards:
        seat = card["seat"]
        player = (
            fresh_players.get(seat)
            or cached_players.get(seat)
        )

        if player is None:
            player = {
                "seat": seat,
                "name": "",
                "stack_text": "",
                "stack_bb": None,
                "is_hero": seat == "hero",
                "is_active": True,
                "occupancy_confidence": float(
                    card["occupancy_confidence"]
                ),
            }

        local_stack = stack_readings[seat]

        if local_stack["stack_bb"] is not None:
            player["stack_bb"] = local_stack[
                "stack_bb"
            ]
            player["stack_text"] = local_stack[
                "stack_text"
            ]

        player["stack_confidence"] = local_stack[
            "confidence"
        ]
        player["stack_read_mode"] = local_stack[
            "mode"
        ]

        players.append(player)

    result = {
        "dealer_button_seat": dealer,
        "players": players,
        "occupied_seats": [
            card["seat"]
            for card in cards
        ],
        "confidence": confidence,
        "source": "snapshot_v2",
    }

    timings = {
        "prepare_ms": prepare_ms,
        "dealer_ms": dealer_ms,
        "payload_ms": payload_ms,
        "api_ms": api_ms,
        "parse_ms": parse_ms,
        "stack_ms": stack_ms,
        "total_ms": (
            perf_counter() - total_t0
        ) * 1000.0,
        "image_count": len(changed_cards),
        "seat_card_count": len(cards),
        "image_bytes": image_bytes,
        "cache_hits": len(cards) - len(changed_cards),
        "cache_misses": len(changed_cards),
    }

    return result, timings
