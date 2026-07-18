from pathlib import Path
from time import perf_counter
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.api.board_reader_core import read_board

BOARD_READER = ROOT / "src/api/board_api_reader.py"
REQUEST_LOG = ROOT / "runtime/live/board_requests.jsonl"
RESULT_LOG = ROOT / "runtime/live/board_results.jsonl"


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload) + "\n")
        f.flush()


def write_result(payload):
    append_jsonl(RESULT_LOG, payload)

    log_latency(
        "worker_finished",
        request_id=payload.get("request_id"),
        worker="board",
        hand_token=payload.get("hand_token"),
        expected_len=payload.get("expected_len"),
        ok=payload.get("ok"),
        error=payload.get("error"),
        elapsed_ms=payload.get("elapsed_ms"),
        board=payload.get("board"),
    )


def run_board_reader(frame):
    t0 = perf_counter()

    try:
        data, timings = read_board(frame)
    except Exception as exc:
        elapsed_ms = (perf_counter() - t0) * 1000.0

        print(
            f"[BOARD_WORKER] in-process reader failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            f"[PROFILE] BOARD_WORKER "
            f"total={elapsed_ms:.1f}ms failed=true",
            flush=True,
        )

        return None, elapsed_ms

    elapsed_ms = (perf_counter() - t0) * 1000.0

    print(
        f"[PROFILE] BOARD_WORKER "
        f"total={elapsed_ms:.1f}ms "
        f"prepare={timings['prepare_ms']:.1f}ms "
        f"encode={timings['encode_ms']:.1f}ms "
        f"api={timings['api_ms']:.1f}ms "
        f"parse={timings['parse_ms']:.1f}ms "
        f"mode={timings['image_mode']}",
        flush=True,
    )

    return data, elapsed_ms


import re

CARD_RE = re.compile(r"^(?:[2-9TJQKA][cdhs])$")

def board_is_valid(board, expected_len):
    if len(board) != expected_len:
        return False, "wrong_length"

    if len(set(board)) != len(board):
        return False, "duplicate_cards"

    for card in board:
        if not CARD_RE.match(card):
            return False, "invalid_card"

    return True, None



def process_request(request):
    request_id = request.get("request_id")
    hand_token = request.get("hand_token")
    expected_len = request.get("expected_len")
    frame_text = request.get("frame")

    if not request_id:
        print("[BOARD_WORKER] ignored request without request_id", flush=True)
        return

    if expected_len not in (3, 4, 5):
        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": "invalid_expected_len",
            "ts": time.time(),
        })
        return

    if not frame_text:
        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": "missing_frame",
            "ts": time.time(),
        })
        return

    frame = Path(frame_text)
    if not frame.exists():
        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": "frame_not_found",
            "frame": str(frame),
            "ts": time.time(),
        })
        return

    print(
        f"[BOARD_WORKER] request={request_id} "
        f"expected={expected_len} frame={frame.name}",
        flush=True,
    )

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="board",
        hand_token=hand_token,
        expected_len=expected_len,
        frame=str(frame),
    )

    data, elapsed_ms = run_board_reader(frame)

    if not data:
        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": "reader_failed",
            "elapsed_ms": elapsed_ms,
            "ts": time.time(),
        })
        return

    board = data.get("board") or []

    if len(board) < expected_len:
        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": "board_too_short",
            "board": board,
            "confidence": data.get("confidence"),
            "elapsed_ms": elapsed_ms,
            "ts": time.time(),
        })
        return

    accepted = board[:expected_len]

    ok, reason = board_is_valid(accepted, expected_len)

    if not ok:
        print(
            f"[BOARD_WORKER] rejected invalid board: {accepted} reason={reason}",
            flush=True,
        )

        write_result({
            "type": "board_result",
            "request_id": request_id,
            "hand_token": hand_token,
            "expected_len": expected_len,
            "ok": False,
            "error": reason,
            "board": accepted,
            "elapsed_ms": elapsed_ms,
            "ts": time.time(),
        })
        return

    write_result({
        "type": "board_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "expected_len": expected_len,
        "ok": True,
        "board": accepted,
        "observed_board_len": len(board),
        "confidence": data.get("confidence"),
        "elapsed_ms": elapsed_ms,
        "ts": time.time(),
    })

    print(
        f"[BOARD_WORKER] completed request={request_id} "
        f"board={' '.join(board[:expected_len])}",
        flush=True,
    )


def main():
    print("api_board_worker running. Ctrl+C to stop.", flush=True)

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
                    print("[BOARD_WORKER] ignored invalid request JSON", flush=True)
                    continue

                request_id = request.get("request_id")
                if request_id in processed_request_ids:
                    continue

                if request_id:
                    processed_request_ids.add(request_id)

                process_request(request)


if __name__ == "__main__":
    main()
