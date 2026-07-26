from pathlib import Path
import json
import statistics

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "runtime/live/perception_latency.jsonl"

if not LOG.exists():
    raise SystemExit("No perception_latency.jsonl found.")

records = []

with LOG.open() as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue

        if rec.get("event") != "end":
            continue

        records.append(rec)

if not records:
    raise SystemExit("No completed latency events found.")

groups = {}

for rec in records:
    groups.setdefault(rec["stage"], []).append(rec["duration_ms"])

overall = sum(
    statistics.mean(v)
    for v in groups.values()
)

print()
print("=" * 94)
print("PIPELINE LATENCY SUMMARY")
print("=" * 94)
print()

header = (
    f'{"Stage":<24}'
    f'{"Runs":>6}'
    f'{"Avg(ms)":>12}'
    f'{"Median":>12}'
    f'{"P95":>12}'
    f'{"Max":>12}'
    f'{"%Total":>10}'
)

print(header)
print("-" * len(header))

ranking = []

for stage, vals in groups.items():

    vals = sorted(vals)

    avg = statistics.mean(vals)
    med = statistics.median(vals)

    if len(vals) == 1:
        p95 = vals[0]
    else:
        idx = int(0.95 * (len(vals)-1))
        p95 = vals[idx]

    mx = max(vals)

    pct = 100.0 * avg / overall if overall else 0.0

    ranking.append((avg, stage))

    print(
        f"{stage:<24}"
        f"{len(vals):>6}"
        f"{avg:>12.1f}"
        f"{med:>12.1f}"
        f"{p95:>12.1f}"
        f"{mx:>12.1f}"
        f"{pct:>9.1f}%"
    )

print()
print("=" * 94)
print("OPTIMIZATION PRIORITY")
print("=" * 94)

ranking.sort(reverse=True)

for avg, stage in ranking:
    bars = "█" * max(1, round(avg / ranking[0][0] * 40))
    print(f"{stage:<24} {bars} {avg:.1f} ms")

print("=" * 94)
