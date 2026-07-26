from pathlib import Path
import json
import statistics

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "runtime/live/snapshot_latency.jsonl"

if not LOG.exists():
    raise SystemExit("snapshot_latency.jsonl not found")

rows = []

with LOG.open() as f:
    for line in f:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass

if not rows:
    raise SystemExit("no snapshot records")

FIELDS = [
    "total_ms",
    "primary_api_ms",
    "retry_api_ms",
    "images",
    "image_kb",
    "retry_count",
]

print()
print("=" * 78)
print("SNAPSHOT LATENCY BREAKDOWN")
print("=" * 78)

for field in FIELDS:
    values = [r[field] for r in rows if field in r]

    if not values:
        continue

    if isinstance(values[0], (int, float)):
        print(
            f"{field:<20}"
            f"avg={statistics.mean(values):8.1f}  "
            f"min={min(values):8.1f}  "
            f"max={max(values):8.1f}"
        )
    else:
        print(field)

print("=" * 78)
