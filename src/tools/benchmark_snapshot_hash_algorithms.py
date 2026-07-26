from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.snapshot_cache import (
    MAX_HASH_DISTANCE,
    _hash_distance,
)
from src.api.table_snapshot_reader_core_v2 import (
    GEOMETRY,
    _prepare,
)


CAPTURE_DIR = ROOT / "runtime/window_captures"
SAMPLE_EVERY = 10
MAX_FRAMES = 200


def full_seat_crop(card):
    seat = card["seat"]
    region = GEOMETRY["seat_regions"][seat]
    bounds = card["bounds"]

    x1 = int(region["x"]) - bounds["x1"]
    y1 = int(region["y"]) - bounds["y1"]
    x2 = x1 + int(region["width"])
    y2 = y1 + int(region["height"])

    crop = card["image"][y1:y2, x1:x2]

    if crop.size == 0:
        raise ValueError(
            f"empty crop for {seat}: "
            f"x1={x1}, y1={y1}, x2={x2}, y2={y2}"
        )

    return crop


def bits_to_hex(bits):
    value = 0

    for bit in bits.flatten():
        value = (value << 1) | int(bool(bit))

    return f"{value:016x}"


def dhash(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(
        gray,
        (9, 8),
        interpolation=cv2.INTER_AREA,
    )

    return bits_to_hex(
        small[:, 1:] > small[:, :-1]
    )


def normalized_dhash(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    normalized = cv2.equalizeHist(gray)

    small = cv2.resize(
        normalized,
        (9, 8),
        interpolation=cv2.INTER_AREA,
    )

    return bits_to_hex(
        small[:, 1:] > small[:, :-1]
    )


def ahash(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(
        gray,
        (8, 8),
        interpolation=cv2.INTER_AREA,
    )

    return bits_to_hex(
        small > small.mean()
    )


def phash(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    resized = cv2.resize(
        gray,
        (32, 32),
        interpolation=cv2.INTER_AREA,
    ).astype(np.float32)

    transformed = cv2.dct(resized)

    low = transformed[:8, :8].copy()

    # Exclude the DC coefficient from the median because it represents
    # overall brightness rather than visual structure.
    median = np.median(low.flatten()[1:])

    bits = low > median
    bits[0, 0] = False

    return bits_to_hex(bits)


HASHERS = {
    "dhash_current": dhash,
    "dhash_equalized": normalized_dhash,
    "ahash": ahash,
    "phash": phash,
}


def new_stats():
    return {
        "last_hash": {},
        "seen": set(),
        "seat_hits": defaultdict(int),
        "seat_misses": defaultdict(int),
        "seat_total": defaultdict(int),
        "total_hits": 0,
        "total_misses": 0,
        "total_total": 0,
        "collision_count": 0,
        "collision_examples": [],
    }


def observe(stats, seat, current_hash):
    if seat not in stats["seen"]:
        stats["last_hash"][seat] = current_hash
        stats["seen"].add(seat)
        return

    stats["seat_total"][seat] += 1
    stats["total_total"] += 1

    distance = _hash_distance(
        stats["last_hash"][seat],
        current_hash,
    )

    if distance <= MAX_HASH_DISTANCE:
        stats["seat_hits"][seat] += 1
        stats["total_hits"] += 1
        return

    stats["seat_misses"][seat] += 1
    stats["total_misses"] += 1

    # Sequential benchmark: after a miss, refresh the reference.
    stats["last_hash"][seat] = current_hash


def print_stats(name, stats):
    print()
    print(f"================ {name} ================")

    for seat in sorted(stats["seat_total"]):
        hits = stats["seat_hits"][seat]
        misses = stats["seat_misses"][seat]
        total = stats["seat_total"][seat]

        percentage = (
            hits * 100.0 / total
            if total
            else 0.0
        )

        print(
            f"{seat:18} "
            f"hits={hits:4} "
            f"misses={misses:4} "
            f"total={total:4} "
            f"{percentage:6.2f}%"
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

    print(
        "Same-frame cross-seat hashes within threshold: "
        f"{stats['collision_count']}"
    )

    if stats["collision_examples"]:
        print("First collision examples:")

        for item in stats["collision_examples"]:
            print(
                f"{item['frame']}: "
                f"{item['first']} vs {item['second']} "
                f"distance={item['distance']}"
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

    all_stats = {
        name: new_stats()
        for name in HASHERS
    }

    for frame in captures:
        _, cards = _prepare(frame)

        frame_hashes = {
            name: {}
            for name in HASHERS
        }

        for card in cards:
            seat = card["seat"]
            crop = full_seat_crop(card)

            for name, hasher in HASHERS.items():
                current_hash = hasher(crop)

                observe(
                    all_stats[name],
                    seat,
                    current_hash,
                )

                frame_hashes[name][seat] = current_hash

        for name in HASHERS:
            seat_hashes = frame_hashes[name]
            stats = all_stats[name]

            for first, second in combinations(
                sorted(seat_hashes),
                2,
            ):
                distance = _hash_distance(
                    seat_hashes[first],
                    seat_hashes[second],
                )

                if distance <= MAX_HASH_DISTANCE:
                    stats["collision_count"] += 1

                    if len(stats["collision_examples"]) < 10:
                        stats["collision_examples"].append({
                            "frame": frame.name,
                            "first": first,
                            "second": second,
                            "distance": distance,
                        })

    for name, stats in all_stats.items():
        print_stats(name, stats)

    print()
    print("================ RANKING ================")

    ranking = []

    for name, stats in all_stats.items():
        percentage = (
            stats["total_hits"] * 100.0 / stats["total_total"]
            if stats["total_total"]
            else 0.0
        )

        ranking.append((
            percentage,
            -stats["collision_count"],
            name,
            stats["collision_count"],
        ))

    ranking.sort(reverse=True)

    for index, (
        percentage,
        _,
        name,
        collision_count,
    ) in enumerate(ranking, start=1):
        print(
            f"{index}. "
            f"{name:18} "
            f"stability={percentage:6.2f}% "
            f"collisions={collision_count}"
        )


if __name__ == "__main__":
    main()
