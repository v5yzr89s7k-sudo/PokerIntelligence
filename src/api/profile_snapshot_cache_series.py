from collections import Counter, defaultdict
from pathlib import Path

from src.api.snapshot_cache import (
    MAX_HASH_DISTANCE,
    _hash_distance,
    image_hash,
)
from src.api.table_snapshot_reader_core_v2 import (
    _cache_fingerprint_image,
    _prepare,
)

CAPTURE_DIR = Path("runtime/window_captures")
MAX_FRAMES = 80


def hashes_for_frame(frame):
    _, cards = _prepare(frame)

    result = {}

    for card in cards:
        crop = _cache_fingerprint_image(card)

        if crop is None or crop.size == 0:
            continue

        result[card["seat"]] = {
            "hash": image_hash(crop),
            "occupied": bool(card["occupied"]),
        }

    return result


captures = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-MAX_FRAMES:]

if len(captures) < 3:
    raise SystemExit("Need at least three saved captures.")

prepared = []

for frame in captures:
    try:
        prepared.append((frame, hashes_for_frame(frame)))
    except Exception as exc:
        print(f"ignored {frame.name}: {exc}")

distances = []
per_seat = defaultdict(list)
threshold_counts = Counter()

print("Snapshot cache series profile")
print("=" * 78)
print("frames:", len(prepared))
print("pairs:", max(0, len(prepared) - 1))
print("current threshold:", MAX_HASH_DISTANCE)
print()

for index in range(1, len(prepared)):
    previous_frame, previous = prepared[index - 1]
    current_frame, current = prepared[index]

    common = sorted(set(previous) & set(current))

    for seat in common:
        before = previous[seat]
        after = current[seat]

        # Only compare continuously occupied seats.
        if not before["occupied"] or not after["occupied"]:
            continue

        distance = _hash_distance(
            before["hash"],
            after["hash"],
        )

        distances.append(distance)
        per_seat[seat].append(distance)

        for threshold in range(0, 13):
            if distance <= threshold:
                threshold_counts[threshold] += 1

if not distances:
    raise SystemExit("No comparable occupied-seat pairs found.")

distances_sorted = sorted(distances)
total = len(distances_sorted)


def percentile(p):
    index = round((total - 1) * p)
    return distances_sorted[index]


print("overall")
print("-" * 78)
print("comparisons:", total)
print("min:", min(distances_sorted))
print("median:", percentile(0.50))
print("p90:", percentile(0.90))
print("p95:", percentile(0.95))
print("p99:", percentile(0.99))
print("max:", max(distances_sorted))
print()

print("hit rate by threshold")
print("-" * 78)

for threshold in range(0, 13):
    hits = threshold_counts[threshold]
    print(
        f"threshold={threshold:2d} "
        f"hits={hits:4d}/{total} "
        f"rate={hits / total * 100.0:6.2f}%"
    )

print()
print("per seat")
print("-" * 78)

for seat in sorted(per_seat):
    values = sorted(per_seat[seat])
    hits = sum(
        distance <= MAX_HASH_DISTANCE
        for distance in values
    )

    print(
        f"{seat:20} "
        f"n={len(values):3d} "
        f"median={values[len(values) // 2]:2d} "
        f"max={max(values):2d} "
        f"hit_rate={hits / len(values) * 100.0:6.2f}%"
    )

print()
print("distance distribution")
print("-" * 78)

for distance, count in sorted(Counter(distances).items()):
    print(f"distance={distance:2d}: {count}")
