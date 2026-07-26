from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.snapshot_cache import (
    _hash_distance,
    image_hash,
)
from src.api.table_snapshot_reader_core_v2 import (
    GEOMETRY,
    _prepare,
)


CAPTURE_DIR = ROOT / "runtime/window_captures"
SAMPLE_EVERY = 10
MAX_FRAMES = 200

THRESHOLDS = list(range(5, 17))


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


def new_stats():
    return {
        "last_hash": {},
        "seen": set(),
        "hits": 0,
        "misses": 0,
        "total": 0,
        "seat_hits": defaultdict(int),
        "seat_total": defaultdict(int),
        "collisions": 0,
        "collision_examples": [],
    }


def observe(stats, seat, current_hash, threshold):
    if seat not in stats["seen"]:
        stats["last_hash"][seat] = current_hash
        stats["seen"].add(seat)
        return

    stats["total"] += 1
    stats["seat_total"][seat] += 1

    distance = _hash_distance(
        stats["last_hash"][seat],
        current_hash,
    )

    if distance <= threshold:
        stats["hits"] += 1
        stats["seat_hits"][seat] += 1
        return

    stats["misses"] += 1
    stats["last_hash"][seat] = current_hash


def main():
    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise SystemExit("No captures")

    captures = captures[::SAMPLE_EVERY][-MAX_FRAMES:]

    print(f"Frames: {len(captures)}")
    print(f"Thresholds: {THRESHOLDS}")

    stats_by_threshold = {
        threshold: new_stats()
        for threshold in THRESHOLDS
    }

    for frame in captures:
        _, cards = _prepare(frame)

        frame_hashes = {}

        for card in cards:
            seat = card["seat"]
            current_hash = image_hash(
                full_seat_crop(card)
            )

            frame_hashes[seat] = current_hash

            for threshold in THRESHOLDS:
                observe(
                    stats_by_threshold[threshold],
                    seat,
                    current_hash,
                    threshold,
                )

        for first, second in combinations(
            sorted(frame_hashes),
            2,
        ):
            distance = _hash_distance(
                frame_hashes[first],
                frame_hashes[second],
            )

            for threshold in THRESHOLDS:
                if distance <= threshold:
                    stats = stats_by_threshold[threshold]
                    stats["collisions"] += 1

                    if len(stats["collision_examples"]) < 5:
                        stats["collision_examples"].append({
                            "frame": frame.name,
                            "first": first,
                            "second": second,
                            "distance": distance,
                        })

    print()
    print(
        "threshold  hits   total  stability  "
        "collisions  delta_vs_5"
    )
    print(
        "---------  -----  -----  ---------  "
        "----------  ----------"
    )

    baseline_pct = None

    for threshold in THRESHOLDS:
        stats = stats_by_threshold[threshold]

        pct = (
            stats["hits"] * 100.0 / stats["total"]
            if stats["total"]
            else 0.0
        )

        if baseline_pct is None:
            baseline_pct = pct

        delta = pct - baseline_pct

        print(
            f"{threshold:9d}  "
            f"{stats['hits']:5d}  "
            f"{stats['total']:5d}  "
            f"{pct:8.2f}%  "
            f"{stats['collisions']:10d}  "
            f"{delta:+9.2f}"
        )

    print()
    print("================ FIRST COLLISION THRESHOLD ================")

    first_collision_threshold = None

    for threshold in THRESHOLDS:
        if stats_by_threshold[threshold]["collisions"]:
            first_collision_threshold = threshold
            break

    if first_collision_threshold is None:
        print("No collisions through maximum tested threshold")
    else:
        stats = stats_by_threshold[first_collision_threshold]

        print(
            f"Threshold: {first_collision_threshold}"
        )
        print(
            f"Collision count: {stats['collisions']}"
        )

        for item in stats["collision_examples"]:
            print(
                f"{item['frame']}: "
                f"{item['first']} vs {item['second']} "
                f"distance={item['distance']}"
            )

    print()
    print("================ BEST ZERO-COLLISION THRESHOLD ================")

    zero_collision_results = []

    for threshold in THRESHOLDS:
        stats = stats_by_threshold[threshold]

        if stats["collisions"] != 0:
            continue

        pct = (
            stats["hits"] * 100.0 / stats["total"]
            if stats["total"]
            else 0.0
        )

        zero_collision_results.append((
            pct,
            threshold,
            stats["hits"],
            stats["total"],
        ))

    if not zero_collision_results:
        print("None")
    else:
        zero_collision_results.sort(reverse=True)

        pct, threshold, hits, total = zero_collision_results[0]

        print(f"Threshold: {threshold}")
        print(f"Stability: {hits}/{total} ({pct:.2f}%)")
        print(
            f"Improvement vs threshold 5: "
            f"{pct - baseline_pct:+.2f} percentage points"
        )


if __name__ == "__main__":
    main()
