from pathlib import Path
from time import perf_counter
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.api.pot_api_reader import read_pot


REQUEST_LOG = ROOT / "runtime/live/pot_requests.jsonl"
RESULT_LOG = ROOT / "runtime/live/pot_results.jsonl"


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a") as handle:
        handle.write(json.dumps(payload) + "\n")
        handle.flush()


def process_request(request):
    request_id = request.get("request_id")
    hand_token = request.get("hand_token")
    frame_text = request.get("frame")

    if not request_id:
        print(
            "[POT_WORKER] ignored request without request_id",
            flush=True,
        )
        return

    if not frame_text:
        append_jsonl(RESULT_LOG, {
            "type": "pot_result",
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
            "type": "pot_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "frame_not_found",
            "frame": str(frame),
            "ts": time.time(),
        })
        return

    print(
        f"[POT_WORKER] request={request_id} frame={frame.name}",
        flush=True,
    )

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="pot",
        hand_token=hand_token,
        frame=str(frame),
    )

    started = perf_counter()

    try:
        data = read_pot(frame)
    except Exception as exc:
        elapsed_ms = (perf_counter() - started) * 1000.0

        append_jsonl(RESULT_LOG, {
            "type": "pot_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": round(elapsed_ms, 1),
            "ts": time.time(),
        })

        print(
            f"[POT_WORKER] failed request={request_id} "
            f"error={type(exc).__name__}: {exc}",
            flush=True,
        )
        return

    elapsed_ms = (perf_counter() - started) * 1000.0
    pot_bb = data.get("pot_bb")

    if not data.get("ok") or pot_bb is None:
        append_jsonl(RESULT_LOG, {
            "type": "pot_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "ok": False,
            "error": "invalid_pot_read",
            "pot_bb": pot_bb,
            "raw_text": data.get("raw_text"),
            "elapsed_ms": round(elapsed_ms, 1),
            "ts": time.time(),
        })
        return

    append_jsonl(RESULT_LOG, {
        "type": "pot_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "ok": True,
        "pot_bb": float(pot_bb),
        "raw_text": data.get("raw_text"),
        "canonical_frame": str(frame),
        "elapsed_ms": round(elapsed_ms, 1),
        "ts": time.time(),
    })

    log_latency(
        "worker_finished",
        request_id=request_id,
        worker="pot",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=round(elapsed_ms, 1),
        pot_bb=float(pot_bb),
    )

    print(
        f"[POT_WORKER] completed request={request_id} "
        f"pot={float(pot_bb):.2f} BB "
        f"elapsed={elapsed_ms:.1f}ms",
        flush=True,
    )


def main():
    print("api_pot_worker running. Ctrl+C to stop.", flush=True)

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

        with REQUEST_LOG.open("r") as handle:
            handle.seek(offset)

            while True:
                line_start = handle.tell()
                line = handle.readline()

                if not line:
                    break

                if not line.endswith("\n"):
                    handle.seek(line_start)
                    break

                offset = handle.tell()

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        "[POT_WORKER] ignored invalid request JSON",
                        flush=True,
                    )
                    continue

                request_id = request.get("request_id")

                if request_id in processed_request_ids:
                    continue

                if request_id:
                    processed_request_ids.add(request_id)

                process_request(request)


if __name__ == "__main__":
    main()
