from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.snapshot_cache import (
    MAX_HASH_DISTANCE,
    _hash_distance,
    image_hash,
    lookup,
    update,
)
from src.api.table_snapshot_reader_core_v2 import (
    GEOMETRY,
    _cache_fingerprint_image,
    _prepare,
)


CAPTURE_DIR = ROOT / "runtime/window_captures"

SAMPLE_EVERY = 10
MAX_FRAMES = 200


def _legacy_full_seat_fingerprint(card):
    """
    Reproduce the original full-seat fingerprint exactly.
    """
    seat = card["seat"]
    seat_rect = GEOMETRY["seat_regions"][seat]
    bounds = card["bounds"]

    x1 = int(seat_rect["x"]) - bounds["x1"]
    y1 = int(seat_rect["y"]) - bounds["y1"]
    x2 = x1 + int(seat_rect["width"])
    y2 = y1 + int(seat_rect["height"])

    image = card["image"][y1:y2, x1:x2]

    if image.size == 0:
        raise ValueError(
            f"empty legacy fingerprint for {seat}: "
            f"x1={x1}, y1={y1}, x2={x2}, y2={y2}"
        )

    return image


def _new_stats():
    return {
        "cache": {},
        "seen": set(),
        "seat_hits": defaultdict(int),
        "seat_misses": defaultdict(int),
        "seat_total": defaultdict(int),
        "total_hits": 0,
        "total_misses": 0,
        "total_total": 0,
    }


def _observe(stats, seat, crop):
    """
    Compare against the most recently accepted fingerprint for this seat.

    First observation seeds the isolated cache and is not scored. A miss
    refreshes the cache so later frames compare against the latest visual
    state rather than an unrelated historical cache entry.
    """
    if seat not in stats["seen"]:
        update(
            stats["cache"],
            seat,
            crop,
            {"name": f"benchmark:{seat}"},
        )
        stats["seen"].add(seat)
        return

    stats["seat_total"][seat] += 1
    stats["total_total"] += 1

    entry = lookup(
        stats["cache"],
        seat,
        crop,
    )

    if entry is not None:
        stats["seat_hits"][seat] += 1
        stats["total_hits"] += 1
        return

    stats["seat_misses"][seat] += 1
    stats["total_misses"] += 1

    update(
        stats["cache"],
        seat,
        crop,
        {"name": f"benchmark:{seat}"},
    )


def _print_stats(title, stats):
    print()
    print(f"================ {title} ================")

    seats = sorted(
        set(stats["seat_total"])
        | set(stats["seat_hits"])
        | set(stats["seat_misses"])
    )

    for seat in seats:
        hits = stats["seat_hits"][seat]
        misses = stats["seat_misses"][seat]
        total = stats["seat_total"][seat]

        pct = (
            hits * 100.0 / total
            if total
            else 0.0
        )

        print(
            f"{seat:18} "
            f"hits={hits:4} "
            f"misses={misses:4} "
            f"total={total:4} "
            f"{pct:6.2f}%"
        )

    overall = (
        stats["total_hits"] * 100.0 / stats["total_total"]
        if stats["total_total"]
        else 0.0
    )

    print()
    print(
        f"Overall: "
        f"{stats['total_hits']}/{stats['total_total']} "
        f"({overall:.2f}%)"
    )


def main():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise SystemExit("No captures")

    captures = captures[::SAMPLE_EVERY][-MAX_FRAMES:]

    print(f"Frames: {len(captures)}")
    print(f"Hash threshold: <= {MAX_HASH_DISTANCE}")

    legacy = _new_stats()
    identity = _new_stats()

    collision_examples = []
    collision_count = 0

    for frame in captures:
        _, cards = _prepare(frame)

        identity_hashes = {}

        for card in cards:
            seat = card["seat"]

            legacy_crop = _legacy_full_seat_fingerprint(card)
            identity_crop = _cache_fingerprint_image(card)

            _observe(
                legacy,
                seat,
                legacy_crop,
            )
            _observe(
                identity,
                seat,
                identity_crop,
            )

            identity_hashes[seat] = image_hash(identity_crop)

        # Identity lookup is seat-scoped, so this cannot directly create a
        # cross-seat cache hit. Still report visually indistinguishable
        # identity crops because they are useful collision-risk evidence.
        for first, second in combinations(
            sorted(identity_hashes),
            2,
        ):
            distance = _hash_distance(
                identity_hashes[first],
                identity_hashes[second],
            )

            if distance <= MAX_HASH_DISTANCE:
                collision_count += 1

                if len(collision_examples) < 20:
                    collision_examples.append({
                        "frame": frame.name,
                        "first": first,
                        "second": second,
                        "distance": distance,
                    })

    _print_stats(
        "LEGACY FULL-SEAT / ISOLATED SEQUENTIAL",
        legacy,
    )
    _print_stats(
        "IDENTITY-ONLY / ISOLATED SEQUENTIAL",
        identity,
    )

    legacy_pct = (
        legacy["total_hits"] * 100.0 / legacy["total_total"]
        if legacy["total_total"]
        else 0.0
    )
    identity_pct = (
        identity["total_hits"] * 100.0 / identity["total_total"]
        if identity["total_total"]
        else 0.0
    )

    print()
    print("================ COMPARISON ================")
    print(f"Legacy:       {legacy_pct:.2f}%")
    print(f"Identity:     {identity_pct:.2f}%")
    print(f"Change:      {identity_pct - legacy_pct:+.2f} percentage points")

    print()
    print("================ COLLISION RISK ================")
    print(
        "Same-frame cross-seat identity hashes "
        f"within threshold: {collision_count}"
    )

    if collision_examples:
        print("First examples:")

        for item in collision_examples:
            print(
                f"{item['frame']}: "
                f"{item['first']} vs {item['second']} "
                f"distance={item['distance']}"
            )
    else:
        print("Examples: none")


if __name__ == "__main__":
    main()
