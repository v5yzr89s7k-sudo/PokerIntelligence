from pathlib import Path
import argparse
import json
import statistics

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "runtime/live/snapshot_latency.jsonl"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--last",
    type=int,
    default=None,
    help="Analyze only the latest N snapshot records.",
)
parser.add_argument(
    "--since-ts",
    type=float,
    default=None,
    help="Analyze records at or after this Unix timestamp.",
)
args = parser.parse_args()

if not LOG.exists():
    raise SystemExit("snapshot_latency.jsonl not found")

rows = []

with LOG.open() as f:
    for line in f:
        try:
            record = json.loads(line)
        except Exception:
            continue

        if isinstance(record, dict):
            rows.append(record)

if args.since_ts is not None:
    rows = [
        row
        for row in rows
        if float(row.get("ts") or 0) >= args.since_ts
    ]

if args.last is not None:
    if args.last <= 0:
        raise SystemExit("--last must be greater than zero")
    rows = rows[-args.last:]

if not rows:
    raise SystemExit("no snapshot records")

fields = [
    "total_ms",
    "primary_api_ms",
    "retry_api_ms",
    "images",
    "image_kb",
    "retry_count",
]

print()
print("=" * 78)
print(
    "SNAPSHOT LATENCY BREAKDOWN "
    f"(records={len(rows)})"
)
print("=" * 78)

for field in fields:
    values = [
        row[field]
        for row in rows
        if isinstance(row.get(field), (int, float))
    ]

    if not values:
        continue

    print(
        f"{field:<20}"
        f"avg={statistics.mean(values):8.1f}  "
        f"median={statistics.median(values):8.1f}  "
        f"min={min(values):8.1f}  "
        f"max={max(values):8.1f}"
    )

print("=" * 78)
