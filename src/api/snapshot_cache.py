from pathlib import Path
import hashlib
import json

import cv2

CACHE_FILE = Path("runtime/live/snapshot_cache.json")
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

MAX_HASH_DISTANCE = 5


def image_hash(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(
        gray,
        (9, 8),
        interpolation=cv2.INTER_AREA,
    )

    differences = small[:, 1:] > small[:, :-1]

    value = 0
    for bit in differences.flatten():
        value = (value << 1) | int(bit)

    return f"{value:016x}"


def _hash_distance(first, second):
    try:
        value = int(first, 16) ^ int(second, 16)
        return bin(value).count("1")
    except (TypeError, ValueError):
        return 64


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(
        json.dumps(cache, indent=2)
    )


def lookup(cache, seat, crop):
    current_hash = image_hash(crop)
    entry = cache.get(seat)

    if not entry:
        return None

    cached_hash = entry.get("hash")

    if (
        _hash_distance(
            cached_hash,
            current_hash,
        )
        <= MAX_HASH_DISTANCE
    ):
        return entry

    return None


def update(cache, seat, crop, data):
    entry = dict(cache.get(seat) or {})

    entry.update({
        "hash": image_hash(crop),
        **data,
    })

    cache[seat] = entry


def stack_image_hash(crop):
    return hashlib.md5(
        crop.tobytes()
    ).hexdigest()


def stack_lookup(cache, seat, crop):
    entry = cache.get(seat)

    if not entry:
        return None

    # Legacy cache records stored only the parsed value and image hash.
    # They must not be promoted to trusted stack readings because their
    # original OCR confidence, vote count, and resolution mode are unknown.
    required_trust_fields = {
        "confidence",
        "votes",
        "mode",
    }

    if not required_trust_fields.issubset(entry):
        return None

    try:
        stack_bb = float(entry.get("stack_bb"))
        confidence = float(entry.get("confidence") or 0.0)
        votes = int(entry.get("votes") or 0)
    except (TypeError, ValueError):
        return None

    if (
        stack_bb <= 0.0
        or confidence < 0.95
        or votes < 2
    ):
        return None

    if entry.get("stack_hash") == stack_image_hash(crop):
        return entry

    return None


def stack_update(cache, seat, crop, data):
    entry = dict(cache.get(seat) or {})

    entry.update({
        "stack_hash": stack_image_hash(crop),
        **data,
    })

    cache[seat] = entry
