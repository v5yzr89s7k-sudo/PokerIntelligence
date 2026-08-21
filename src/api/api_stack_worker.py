from pathlib import Path
import json
import sys
import time

import cv2


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)


REQUESTS = ROOT / "runtime/live/stack_requests.jsonl"
RESULTS = ROOT / "runtime/live/stack_results.jsonl"

GEOM = json.loads(
    (ROOT / "config/geometry.json").read_text()
)


def append_jsonl(path, item):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open("a") as handle:
        handle.write(json.dumps(item) + "\n")
        handle.flush()


def crop_stack(frame_path, seat):
    img = cv2.imread(str(frame_path))

    if img is None:
        return None

    # Recorded/live source frames may not already be canonical.
    if img.shape[1] != 934 or img.shape[0] != 696:
        img = cv2.resize(
            img,
            (934, 696),
            interpolation=cv2.INTER_AREA,
        )

    region = (
        GEOM.get("stack_regions", {})
        .get(seat)
    )

    if not isinstance(region, dict):
        return None

    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    crop = img[y:y + h, x:x + w]

    if crop is None or crop.size == 0:
        return None

    return crop


def process_request(request):
    started = time.perf_counter()

    request_id = request.get("request_id")
    hand_token = request.get("hand_token")
    seat = request.get("seat")
    street = request.get("street")
    frame = request.get("frame")
    purpose = request.get("purpose")

    result = {
        "type": "stack_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "seat": seat,
        "street": street,
        "frame": frame,
        "purpose": purpose,
        "ok": False,
        "reading": None,
        "independent": None,
        "error": None,
    }

    try:
        crop = crop_stack(
            frame,
            seat,
        )

        if crop is None:
            result["error"] = "invalid_stack_crop"
        else:
            # Return raw perception families. The worker deliberately does
            # not apply canonical continuity or poker semantics.
            if purpose == "baseline":
                independent = (
                    read_stack_independent_consensus(crop)
                    or {}
                )

                result["independent"] = independent
                result["ok"] = True

            else:
                reading = read_stack(crop) or {}
                independent = (
                    read_stack_independent_consensus(crop)
                    or {}
                )

                result["reading"] = reading
                result["independent"] = independent
                result["ok"] = True

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

    return result


def main():
    REQUESTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REQUESTS.touch(exist_ok=True)
    RESULTS.touch(exist_ok=True)

    offset = 0
    processed = set()

    print(
        "api_stack_worker running. Ctrl+C to stop.",
        flush=True,
    )

    while True:
        try:
            size = REQUESTS.stat().st_size

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
                        != "stack_request"
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

                    result = process_request(
                        request
                    )

                    append_jsonl(
                        RESULTS,
                        result,
                    )

                    log_latency(
                        "worker_result",
                        worker="stack",
                        request_id=request_id,
                        hand_token=result.get(
                            "hand_token"
                        ),
                        seat=result.get("seat"),
                        street=result.get("street"),
                        purpose=result.get("purpose"),
                        ok=result.get("ok"),
                        elapsed_ms=result.get(
                            "elapsed_ms"
                        ),
                    )

                    print(
                        "[STACK_WORKER]",
                        f"request={request_id[:8]}",
                        f"seat={result.get('seat')}",
                        f"street={result.get('street')}",
                        f"purpose={result.get('purpose')}",
                        f"elapsed={result.get('elapsed_ms')}ms",
                        flush=True,
                    )

        except Exception as exc:
            print(
                "[STACK_WORKER]",
                f"loop error={exc}",
                flush=True,
            )

        time.sleep(0.05)


if __name__ == "__main__":
    main()
