from pathlib import Path
import json
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


from src.api.bet_amount_api_reader import (
    read_bet_amount,
)
from src.api.perception_latency import log as log_latency

REQUESTS = (
    ROOT
    / "runtime/live/bet_amount_requests.jsonl"
)

RESULTS = (
    ROOT
    / "runtime/live/bet_amount_results.jsonl"
)


def append_jsonl(path, item):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("a") as handle:
        handle.write(
            json.dumps(item) + "\n"
        )
        handle.flush()


def process_request(request):
    request_id = request.get("request_id")
    frame = request.get("frame")
    seat = request.get("seat")
    street = request.get("street")
    hand_token = request.get("hand_token")

    started = time.perf_counter()

    result = {
        "type": "bet_amount_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "seat": seat,
        "street": street,
        "frame": frame,
        "ok": False,
        "bet_bb": None,
        "raw_text": None,
        "error": None,
    }

    try:
        reading = read_bet_amount(
            frame,
            seat,
        )

        result["bet_bb"] = reading.get(
            "bet_bb"
        )
        result["raw_text"] = reading.get(
            "raw_text"
        )

        result["ok"] = (
            result["bet_bb"] is not None
        )

    except Exception as exc:
        result["error"] = str(exc)

    result["elapsed_ms"] = round(
        (
            time.perf_counter()
            - started
        )
        * 1000.0,
        1,
    )

    result["ts"] = time.time()

    append_jsonl(
        RESULTS,
        result,
    )

    log_latency(
        "worker_result",
        worker="bet_amount",
        request_id=request_id,
        hand_token=hand_token,
        seat=seat,
        street=street,
        ok=result["ok"],
        elapsed_ms=result["elapsed_ms"],
    )


def main():
    REQUESTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REQUESTS.touch(exist_ok=True)
    RESULTS.touch(exist_ok=True)

    offset = 0
    processed = set()

    while True:
        try:
            size = REQUESTS.stat().st_size

            # Runner reset can truncate the file while this worker lives.
            if size < offset:
                offset = 0
                processed.clear()

            with REQUESTS.open("r") as handle:
                handle.seek(offset)

                while True:
                    position = handle.tell()
                    raw = handle.readline()

                    if not raw:
                        break

                    # Never consume a partially appended JSONL record.
                    if not raw.endswith("\n"):
                        handle.seek(position)
                        break

                    offset = handle.tell()

                    try:
                        request = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    if (
                        request.get("type")
                        != "bet_amount_request"
                    ):
                        continue

                    request_id = request.get(
                        "request_id"
                    )

                    if (
                        not request_id
                        or request_id in processed
                    ):
                        continue

                    processed.add(request_id)
                    process_request(request)

        except Exception as exc:
            print(
                "[BET_AMOUNT_WORKER]",
                f"loop error={exc}",
                flush=True,
            )

        time.sleep(0.05)


if __name__ == "__main__":
    main()
