from pathlib import Path
from time import perf_counter
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.api.hero_cards_reader_core import read_hero_cards

HERO_READER = ROOT / "src/api/hero_cards_api_reader.py"
REQUEST_LOG = ROOT / "runtime/live/hero_requests.jsonl"
RESULT_LOG = ROOT / "runtime/live/hero_results.jsonl"


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
        f.flush()


def run_hero_reader(frame):
    t0 = perf_counter()

    try:
        data, timings = read_hero_cards(frame)
    except Exception as exc:
        elapsed_ms = (perf_counter() - t0) * 1000.0
        print(
            f"[HERO_WORKER] in-process reader failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            f"[PROFILE] HERO_WORKER total={elapsed_ms:.1f}ms failed=true",
            flush=True,
        )
        return None, elapsed_ms

    elapsed_ms = (perf_counter() - t0) * 1000.0

    print(
        f"[PROFILE] HERO_WORKER "
        f"total={elapsed_ms:.1f}ms "
        f"prepare={timings['prepare_ms']:.1f}ms "
        f"encode={timings['encode_ms']:.1f}ms "
        f"api={timings['api_ms']:.1f}ms "
        f"parse={timings['parse_ms']:.1f}ms "
        f"mode={timings['image_mode']}",
        flush=True,
    )

    return data, elapsed_ms


def process_request(request):
    request_id = request.get("request_id")
    hand_token = request.get("hand_token")
    frame_text = request.get("frame")

    if not request_id:
        print("[HERO_WORKER] ignored request without request_id", flush=True)
        return

    if not frame_text:
        append_jsonl(RESULT_LOG, {
            "type": "hero_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "missing_frame",
            "ts": time.time(),
        })
        return

    frame = Path(frame_text)

    if not frame.exists():
        append_jsonl(RESULT_LOG, {
            "type": "hero_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "frame_not_found",
            "frame": str(frame),
            "ts": time.time(),
        })
        return

    print(
        f"[HERO_WORKER] request={request_id} frame={frame.name}",
        flush=True,
    )

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="hero",
        hand_token=hand_token,
        frame=str(frame),
    )

    data, elapsed_ms = run_hero_reader(frame)

    if not data:
        append_jsonl(RESULT_LOG, {
            "type": "hero_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "reader_failed",
            "elapsed_ms": elapsed_ms,
            "ts": time.time(),
        })
        return

    cards = data.get("hero_cards") or []

    if len(cards) != 2 or not all(cards):
        append_jsonl(RESULT_LOG, {
            "type": "hero_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "invalid_cards",
            "hero_cards": cards,
            "confidence": data.get("confidence"),
            "elapsed_ms": elapsed_ms,
            "ts": time.time(),
        })
        return

    append_jsonl(RESULT_LOG, {
        "type": "hero_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "ok": True,
        "hero_cards": cards,
        "confidence": data.get("confidence"),
        "elapsed_ms": elapsed_ms,
        "ts": time.time(),
    })

    log_latency(
        "worker_finished",
        request_id=request_id,
        worker="hero",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=elapsed_ms,
        hero_cards=cards,
    )

    print(
        f"[HERO_WORKER] completed request={request_id} "
        f"cards={' '.join(cards)}",
        flush=True,
    )


def main():
    print("api_hero_worker running. Ctrl+C to stop.", flush=True)

    offset = 0
    processed_request_ids = set()

    while True:
        if not REQUEST_LOG.exists():
            offset = 0
            time.sleep(0.05)
            continue

        size = REQUEST_LOG.stat().st_size

        if size < offset:
            offset = 0
            processed_request_ids.clear()

        if size == offset:
            time.sleep(0.05)
            continue

        with REQUEST_LOG.open("r") as f:
            f.seek(offset)

            while True:
                line_start = f.tell()
                line = f.readline()

                if not line:
                    break

                if not line.endswith("\n"):
                    f.seek(line_start)
                    break

                offset = f.tell()

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    print("[HERO_WORKER] ignored invalid request JSON", flush=True)
                    continue

                request_id = request.get("request_id")

                if request_id in processed_request_ids:
                    continue

                if request_id:
                    processed_request_ids.add(request_id)

                process_request(request)


if __name__ == "__main__":
    main()
