from pathlib import Path
import json
import time

ROOT = Path(__file__).resolve().parents[2]
LATENCY = ROOT / "runtime/live/perception_latency.jsonl"


def log(stage, request_id=None, worker=None, **extra):
    LATENCY.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": time.time(),
        "stage": stage,
    }

    if request_id:
        payload["request_id"] = request_id

    if worker:
        payload["worker"] = worker

    payload.update(extra)

    with LATENCY.open("a") as f:
        f.write(json.dumps(payload) + "\n")
        f.flush()
