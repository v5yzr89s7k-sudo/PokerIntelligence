from pathlib import Path
from time import perf_counter
import json
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
LATENCY = ROOT / "runtime/live/perception_latency.jsonl"

_LOCK = threading.Lock()
_ACTIVE = {}


def _append(payload):
    LATENCY.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        with LATENCY.open("a") as f:
            f.write(json.dumps(payload, separators=(",", ":")))
            f.write("\n")
            f.flush()


def log(stage, request_id=None, worker=None, **extra):
    payload = {
        "ts": time.time(),
        "stage": stage,
    }

    if request_id:
        payload["request_id"] = request_id

    if worker:
        payload["worker"] = worker

    payload.update(extra)

    _append(payload)


def begin(trace_id, stage, **extra):
    _ACTIVE[(trace_id, stage)] = perf_counter()

    payload = {
        "ts": time.time(),
        "event": "begin",
        "trace": trace_id,
        "stage": stage,
    }

    payload.update(extra)

    _append(payload)


def end(trace_id, stage, **extra):
    key = (trace_id, stage)

    started = _ACTIVE.pop(key, None)

    if started is None:
        return

    payload = {
        "ts": time.time(),
        "event": "end",
        "trace": trace_id,
        "stage": stage,
        "duration_ms": round(
            (perf_counter() - started) * 1000.0,
            3,
        ),
    }

    payload.update(extra)

    _append(payload)
