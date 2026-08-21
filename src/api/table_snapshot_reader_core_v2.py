from pathlib import Path
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import base64
import copy
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
from src.vision.stack_reader import read_stack, read_stack_independent_consensus
from src.api.snapshot_cache import (
    load_cache,
    save_cache,
    lookup as cache_lookup,
    update as cache_update,
    stack_lookup,
    stack_update,
)
from src.identity.identity_manager import IdentityManager


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

    # Physical geometry labels are metadata, never player names.
    "SEAT_TOP",
    "SEAT_UPPER_RIGHT",
    "SEAT_MID_RIGHT",
    "SEAT_LOWER_RIGHT",
    "HERO",
    "SEAT_LOWER_LEFT",
    "SEAT_MID_LEFT",
    "SEAT_UPPER_LEFT",
}

IDENTITY_MANAGER = IdentityManager()


PROMPT_HEADER = """
Read the visible player name from this single ACR physical-seat crop.

Return RAW JSON ONLY:

{
  "name": ""
}

Rules:

- Read only the player name.
- The caller already knows the authoritative physical seat.
- Do not return or infer a seat label.
- Ignore stack text, chip counts, bets, buttons, dealer markers, board cards,
  hole cards, and all other table information.
- Ignore transient action text such as CHECK, FOLD, CALL, BET, RAISE,
  ALL IN, POST SB, POST BB, ANTE, MUCK, SHOW, SITTING OUT, and SIT OUT.
- Never use transient action text as a player name.
- Use an empty string when the name cannot be read confidently.
- Do not infer hidden or partially obscured text.
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


def _prepare(frame_path, dealt_in_seats=None):
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

    authoritative = {
        seat
        for seat in (dealt_in_seats or [])
        if seat
    }

    if authoritative:
        selected_cards = [
            card
            for card in all_cards
            if card["seat"] in authoritative
        ]
    else:
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


def _request_cards_api(cards, dealer):
    """
    Snapshot V3: read one player name from one authoritative seat crop.

    The caller owns seat identity. Local OCR owns stack values.
    """
    if len(cards) != 1:
        raise ValueError(
            "Snapshot V3 requires exactly one seat card per API request"
        )

    card = cards[0]
    seat = card["seat"]

    content, image_bytes = _build_content(cards)

    api_started = perf_counter()

    response = CLIENT.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": content,
        }],
    )

    api_ms = (
        perf_counter() - api_started
    ) * 1000.0

    parse_started = perf_counter()

    data = _extract_json(
        response.output_text
    )

    name = _normalize_name(
        data.get("name")
    )

    player = {
        "seat": seat,
        "name": name,
        "stack_text": "",
        "stack_bb": None,
        "is_hero": seat == "hero",
        "is_active": True,
        "occupancy_confidence": float(
            card.get("occupancy_confidence")
            or 0.0
        ),
    }

    parse_ms = (
        perf_counter() - parse_started
    ) * 1000.0

    return {
        "api_ms": api_ms,
        "parse_ms": parse_ms,
        "image_bytes": image_bytes,
        "players": [player],
        "confidence": (
            1.0
            if name
            else None
        ),
    }


def _request_cards_parallel(cards, dealer):
    if not cards:
        return {
            "api_ms": 0.0,
            "parse_ms": 0.0,
            "image_bytes": 0,
            "players": [],
            "confidence": None,
            "seat_api_ms": {},
            "failures": {},
        }

    wall_started = perf_counter()
    max_workers = min(8, len(cards))
    deadline_seconds = 3.5

    players_by_seat = {}
    confidences = []
    seat_api_ms = {}
    failures = {}
    total_parse_ms = 0.0
    total_image_bytes = 0

    executor = ThreadPoolExecutor(
        max_workers=max_workers
    )

    futures = {
        executor.submit(
            _request_cards_api,
            [card],
            dealer,
        ): card["seat"]
        for card in cards
    }

    try:
        for future in as_completed(
            futures,
            timeout=deadline_seconds,
        ):
            seat = futures[future]

            try:
                result = future.result()
            except Exception as exc:
                failures[seat] = (
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            seat_api_ms[seat] = round(
                float(result.get("api_ms") or 0.0),
                1,
            )

            total_parse_ms += float(
                result.get("parse_ms") or 0.0
            )
            total_image_bytes += int(
                result.get("image_bytes") or 0
            )

            confidence = result.get("confidence")
            if isinstance(confidence, (int, float)):
                confidences.append(float(confidence))

            for player in result.get("players") or []:
                player_seat = player.get("seat")

                if player_seat == seat:
                    players_by_seat[seat] = player
                    break

    except TimeoutError:
        pass

    finally:
        for future, seat in futures.items():
            if future.done():
                continue

            failures[seat] = (
                f"snapshot_deadline_exceeded:"
                f"{deadline_seconds:.1f}s"
            )
            future.cancel()

        # Do not block snapshot publication on API stragglers.
        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )

    wall_ms = (
        perf_counter() - wall_started
    ) * 1000.0

    # Preserve deterministic seat topology when a request fails or times out.
    # Later cache/local-stack fallback can enrich incomplete seats.
    players = []

    for card in cards:
        seat = card["seat"]
        player = players_by_seat.get(seat)

        if player is None:
            player = {
                "seat": seat,
                "name": "",
                "stack_text": "",
                "stack_bb": None,
                "is_hero": seat == "hero",
                "is_active": True,
            }

        players.append(player)

    confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else None
    )

    print(
        "[SNAPSHOT_PARALLEL] "
        f"seats={len(cards)} "
        f"workers={max_workers} "
        f"deadline={deadline_seconds:.1f}s "
        f"wall={wall_ms:.1f}ms "
        f"failures={len(failures)} "
        f"seat_api_ms={seat_api_ms}",
        flush=True,
    )

    if failures:
        print(
            f"[SNAPSHOT_PARALLEL_FAILURES] {failures}",
            flush=True,
        )

    return {
        "api_ms": wall_ms,
        "parse_ms": total_parse_ms,
        "image_bytes": total_image_bytes,
        "players": players,
        "confidence": confidence,
        "seat_api_ms": seat_api_ms,
        "failures": failures,
    }

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
    stack_rect = GEOMETRY["stack_regions"][seat]
    bounds = card["bounds"]

    x1 = int(seat_rect["x"]) - bounds["x1"]
    y1 = int(seat_rect["y"]) - bounds["y1"]
    x2 = x1 + int(seat_rect["width"])

    # Identity fingerprint excludes the changing stack line.
    stack_start_y = int(stack_rect["y"]) - int(seat_rect["y"])
    fingerprint_height = max(1, stack_start_y - 2)
    y2 = y1 + fingerprint_height

    return card["image"][y1:y2, x1:x2]


def _cache_player(entry, card):
    """
    Build an identity-only cached player record.

    Cached names may remain valid for Hero, but cached stack values are never
    authoritative for a new snapshot. Fresh trusted local OCR owns stacks.
    """
    return {
        "seat": card["seat"],
        "name": _normalize_name(entry.get("name")),
        "stack_text": "",
        "stack_bb": None,
        "is_hero": card["seat"] == "hero",
        "is_active": True,
        "occupancy_confidence": float(card["occupancy_confidence"]),
    }


def retry_unresolved_opponent_names(
    fresh_players,
    missing_name_cards,
    dealer,
):
    """
    Retry each unresolved opponent exactly once using only that
    physical-seat crop.

    This is a bounded recovery path for a per-seat timeout or unreadable
    primary result. It never re-requests already resolved opponents and
    never substitutes cached identity for fresh evidence.
    """
    retry_api_ms = 0.0
    retry_parse_ms = 0.0
    retry_image_bytes = 0
    retry_count = 0

    still_blank = []

    for card in missing_name_cards:
        seat = card["seat"]

        if seat == "hero":
            continue

        retry_count += 1

        try:
            result = _request_cards_api(
                [card],
                dealer,
            )
        except Exception as exc:
            print(
                "[SNAPSHOT_NAME_RETRY_FAILURE] "
                f"seat={seat} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )
            still_blank.append(seat)
            continue

        retry_api_ms += float(
            result.get("api_ms") or 0.0
        )
        retry_parse_ms += float(
            result.get("parse_ms") or 0.0
        )
        retry_image_bytes += int(
            result.get("image_bytes") or 0
        )

        recovered = None

        for player in result.get("players") or []:
            if (
                player.get("seat") == seat
                and player.get("name")
            ):
                recovered = player
                break

        if recovered is None:
            still_blank.append(seat)
            continue

        current = fresh_players.get(seat)

        if current is None:
            fresh_players[seat] = recovered
        else:
            # Retry owns identity recovery only. Local stack OCR remains
            # authoritative for stack values later in snapshot assembly.
            current["name"] = _normalize_name(
                recovered.get("name")
            )

        print(
            "[SNAPSHOT_NAME_RETRY_RECOVERED] "
            f"seat={seat} "
            f"name={fresh_players[seat].get('name')!r}",
            flush=True,
        )

    return {
        "still_blank": sorted(still_blank),
        "api_ms": retry_api_ms,
        "parse_ms": retry_parse_ms,
        "image_bytes": retry_image_bytes,
        "count": retry_count,
    }


def preserve_unresolved_opponent_names(
    fresh_players,
    missing_name_cards,
):
    """
    Leave unresolved opponent names blank.

    Physical seat alone is not identity evidence because players can move
    between hands and tables.
    """
    unresolved = []

    for card in missing_name_cards:
        seat = card["seat"]
        player = fresh_players.get(seat)

        if player is None:
            continue

        player["name"] = ""
        unresolved.append(seat)

    return sorted(unresolved)



def _read_local_stacks(cards, cache_snapshot):
    """
    Read local stacks without mutating the shared snapshot cache.

    This function is safe to run concurrently with the Vision API
    request. Cache updates are returned and applied later by the
    main thread.
    """
    stack_t0 = perf_counter()
    stack_readings = {}
    cache_updates = []

    for card in cards:
        seat = card["seat"]
        region = GEOMETRY["stack_regions"][seat]

        x1 = int(region["x"]) - card["bounds"]["x1"]
        y1 = int(region["y"]) - card["bounds"]["y1"]
        x2 = x1 + int(region["width"])
        y2 = y1 + int(region["height"])

        stack_crop = card["image"][y1:y2, x1:x2]

        cached_stack = stack_lookup(
            cache_snapshot,
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

        stack_candidates = []

        for reading in result.get("raw") or []:
            if not isinstance(reading, dict):
                continue

            value = reading.get("stack_bb")

            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if value <= 0.0:
                continue

            if value not in stack_candidates:
                stack_candidates.append(value)

        result = {
            **result,
            "stack_candidates": stack_candidates,
        }

        trusted_stack = (
            result.get("stack_bb") is not None
            and float(result.get("stack_bb")) > 0.0
            and float(result.get("confidence") or 0.0) >= 0.95
            and int(result.get("votes") or 0) >= 2
        )

        if trusted_stack:
            stack_readings[seat] = result

            cache_updates.append({
                "seat": seat,
                "stack_crop": stack_crop,
                "payload": {
                    "stack_bb": result["stack_bb"],
                    "stack_text": result["stack_text"],
                    "confidence": result["confidence"],
                    "votes": result["votes"],
                    "mode": result["mode"],
                },
            })
        else:
            independent = (
                read_stack_independent_consensus(
                    stack_crop
                )
                or {}
            )

            independent_trusted = (
                independent.get("stack_bb") is not None
                and float(independent.get("stack_bb")) > 0.0
                and float(
                    independent.get("confidence") or 0.0
                ) >= 0.95
                and int(
                    independent.get("votes") or 0
                ) >= 3
            )

            if independent_trusted:
                stack_readings[seat] = independent

                cache_updates.append({
                    "seat": seat,
                    "stack_crop": stack_crop,
                    "payload": {
                        "stack_bb": independent["stack_bb"],
                        "stack_text": independent["stack_text"],
                        "confidence": independent["confidence"],
                        "votes": independent["votes"],
                        "mode": independent["mode"],
                    },
                })
            else:
                stack_readings[seat] = {
                    **result,
                    "stack_bb": None,
                    "stack_text": "",
                }

    stack_ms = (
        perf_counter() - stack_t0
    ) * 1000.0

    return (
        stack_readings,
        cache_updates,
        stack_ms,
    )


def read_table_snapshot_v2(frame, dealt_in_seats=None):
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
        frame_path,
        dealt_in_seats=dealt_in_seats,
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
        fingerprint = _cache_fingerprint_image(card)

        # Hero identity is session-stable. The nameplate is frequently
        # replaced by transient labels such as POST BB, ANTE, FOLD, CALL,
        # CHECK, and RAISE, making visual fingerprint matching unreliable.
        #
        # Preserve the cached Hero identity instead of treating these
        # temporary UI states as a player change.
        if card["seat"] == "hero":
            cached_entry = cache.get("hero")

            identity = IDENTITY_MANAGER.resolve_hero(
                seat="hero",
                cached_entry=cached_entry,
            )

            entry = (
                cached_entry
                if identity.resolved
                else None
            )
        else:
            # Stabilization policy: opponent identity must come from the
            # current snapshot. The existing perceptual fingerprint has not
            # demonstrated discrimination between different players, so it
            # cannot safely authorize cached-name reuse.
            identity = IDENTITY_MANAGER.unresolved(
                seat=card["seat"],
            )
            entry = None

        if entry is None:
            changed_cards.append(card)
        else:
            cached_players[card["seat"]] = (
                _cache_player(entry, card)
            )

    payload_t0 = perf_counter()

    hit_seats = sorted(cached_players.keys())
    miss_seats = sorted(card["seat"] for card in changed_cards)

    print(
        "[SNAPSHOT_CACHE]\n"
        f"  hit={hit_seats}\n"
        f"  miss={miss_seats}\n"
        f"  changed={len(changed_cards)} "
        f"cached={len(cached_players)} "
        f"total={len(cards)}",
        flush=True,
    )

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

    # Local stack OCR is independent of the Vision API.
    # Run it concurrently so its cost is hidden behind API latency.
    stack_executor = ThreadPoolExecutor(max_workers=1)
    stack_future = stack_executor.submit(
        _read_local_stacks,
        cards,
        copy.deepcopy(cache),
    )

    api_ms = 0.0
    parse_ms = 0.0
    primary_api_ms = 0.0
    primary_parse_ms = 0.0
    retry_build_ms = 0.0
    retry_api_ms = 0.0
    retry_parse_ms = 0.0
    retry_count = 0
    retry_image_bytes = 0
    confidence = None
    fresh_players = {}

    if changed_cards:
        parallel_result = _request_cards_parallel(
            changed_cards,
            dealer,
        )

        primary_api_ms = float(
            parallel_result.get("api_ms")
            or 0.0
        )
        api_ms = primary_api_ms

        primary_parse_ms = float(
            parallel_result.get("parse_ms")
            or 0.0
        )

        # Use the actual sum of per-seat JPEG payloads.
        image_bytes = int(
            parallel_result.get("image_bytes")
            or image_bytes
        )

        confidence = parallel_result.get(
            "confidence"
        )

        fresh_players = {
            player["seat"]: player
            for player in (
                parallel_result.get("players")
                or []
            )
        }

        # Retry unreadable opponent names once using only the failed
        # physical-seat crops.
        missing_name_cards = [
            card
            for card in changed_cards
            if card["seat"] != "hero"
            and not fresh_players[
                card["seat"]
            ].get("name")
        ]

        if missing_name_cards:
            retry_result = retry_unresolved_opponent_names(
                fresh_players,
                missing_name_cards,
                dealer,
            )

            retry_count = int(
                retry_result.get("count") or 0
            )
            retry_api_ms = float(
                retry_result.get("api_ms") or 0.0
            )
            retry_parse_ms = float(
                retry_result.get("parse_ms") or 0.0
            )
            retry_image_bytes = int(
                retry_result.get("image_bytes") or 0
            )

            still_blank = retry_result.get(
                "still_blank"
            ) or []

            if still_blank:
                still_blank = preserve_unresolved_opponent_names(
                    fresh_players,
                    [
                        card
                        for card in missing_name_cards
                        if card["seat"] in still_blank
                    ],
                )

                print(
                    "[SNAPSHOT_NAME_UNRESOLVED]",
                    {
                        "requested": still_blank,
                        "policy": "leave_blank_without_verified_fingerprint",
                    },
                    flush=True,
                )

        # Hero identity is stable across hands. A changing visual fingerprint
        # must not erase a previously confirmed Hero name.
        hero_player = fresh_players.get("hero")
        hero_cached = cache.get("hero") or {}

        if (
            hero_player is not None
            and not hero_player.get("name")
            and hero_cached.get("name")
        ):
            hero_player["name"] = hero_cached["name"]

            print(
                "[SNAPSHOT_HERO_NAME_FALLBACK] "
                f"name={hero_cached['name']!r}",
                flush=True,
            )

        for card in changed_cards:
            player = fresh_players[
                card["seat"]
            ]

            cache_payload = {
                "stack_text": player["stack_text"],
                "stack_bb": player["stack_bb"],
            }

            # Never persist an unreadable name. This guarantees another
            # attempt on a future snapshot instead of preserving a blank.
            if player.get("name"):
                cache_payload["name"] = player["name"]

            cache_update(
                cache,
                card["seat"],
                _cache_fingerprint_image(card),
                cache_payload,
            )

        save_cache(cache)
        parse_ms = primary_parse_ms + retry_parse_ms

    players = []

    try:
        (
            stack_readings,
            stack_cache_updates,
            stack_ms,
        ) = stack_future.result()
    finally:
        stack_executor.shutdown(wait=True)

    # Apply stack-cache writes only on the main thread.
    for update in stack_cache_updates:
        stack_update(
            cache,
            update["seat"],
            update["stack_crop"],
            update["payload"],
        )

    save_cache(cache)

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
        player["stack_candidates"] = list(
            local_stack.get("stack_candidates")
            or []
        )

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
        "primary_api_ms": primary_api_ms,
        "primary_parse_ms": primary_parse_ms,
        "retry_build_ms": retry_build_ms,
        "retry_api_ms": retry_api_ms,
        "retry_parse_ms": retry_parse_ms,
        "retry_count": retry_count,
        "retry_image_bytes": retry_image_bytes,
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
