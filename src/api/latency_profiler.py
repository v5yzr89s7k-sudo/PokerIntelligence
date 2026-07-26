from __future__ import annotations

import json
import threading
from pathlib import Path
from time import perf_counter, time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runtime" / "live"
OUT.mkdir(parents=True, exist_ok=True)

LOG = OUT / "pipeline_latency.jsonl"

_lock = threading.Lock()
_active = {}


def begin(trace_id: str, stage: str):
    _active[(trace_id, stage)] = perf_counter()


def end(trace_id: str, stage: str, **meta):
    key = (trace_id, stage)
    start = _active.pop(key, None)
    if start is None:
        return

    record = {
        "ts": time(),
        "trace": trace_id,
        "stage": stage,
        "duration_ms": round((perf_counter() - start) * 1000.0, 3),
    }

    if meta:
        record.update(meta)

    line = json.dumps(record, separators=(",", ":"))

    with _lock:
        with LOG.open("a") as f:
            f.write(line)
            f.write("\n")
