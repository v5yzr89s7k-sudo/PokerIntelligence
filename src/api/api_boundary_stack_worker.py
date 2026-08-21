from pathlib import Path
import json
import sys
import time

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vision.stack_reader import (
    read_stack,
    read_stack_independent_consensus,
)


REQUESTS = ROOT / "runtime/live/boundary_stack_requests.jsonl"
RESULTS = ROOT / "runtime/live/boundary_stack_results.jsonl"
GEOM = json.loads((ROOT / "config/geometry.json").read_text())

MIN_CONFIDENCE = 0.95
MIN_VOTES = 2


def append_jsonl(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a") as handle:
        handle.write(json.dumps(payload) + "\n")
        handle.flush()


def crop_region(img, region):
    x = int(region["x"])
    y = int(region["y"])
    w = int(region["width"])
    h = int(region["height"])

    return img[y:y + h, x:x + w]


def trusted_read(frame_path, seat):
    img = cv2.imread(str(frame_path))

    if img is None:
        return None

    img = cv2.resize(img, (934, 696))

    region = (
        GEOM.get("stack_regions", {})
        .get(seat)
    )

    if not region:
        return None

    crop = crop_region(img, region)

    if crop.size == 0:
        return None

    # Prefer the independent thresholded PSM13 family when it reaches
    # its stronger three-vote consensus. This protects the boundary path
    # from correlated green/plain OCR errors such as Replay 0002's
    # 53.41 -> 93.41 leading-digit failure.
    independent = (
        read_stack_independent_consensus(crop)
        or {}
    )

    independent_stack = independent.get("stack_bb")
    independent_confidence = float(
        independent.get("confidence") or 0.0
    )
    independent_votes = int(
        independent.get("votes") or 0
    )

    if (
        independent_stack is not None
        and independent_confidence >= MIN_CONFIDENCE
        and independent_votes >= 3
    ):
        return {
            "seat": seat,
            "stack_bb": float(independent_stack),
            "confidence": independent_confidence,
            "votes": independent_votes,
            "mode": independent.get(
                "mode",
                "independent_segmentation",
            ),
            "frame_path": str(frame_path),
        }

    # Fall back to the existing ordinary stack reader when independent
    # segmentation does not establish a strong consensus.
    reading = read_stack(crop) or {}

    stack_bb = reading.get("stack_bb")
    confidence = float(reading.get("confidence") or 0.0)
    votes = int(reading.get("votes") or 0)

    if (
        stack_bb is None
        or confidence < MIN_CONFIDENCE
        or votes < MIN_VOTES
    ):
        return None

    return {
        "seat": seat,
        "stack_bb": float(stack_bb),
        "confidence": confidence,
        "votes": votes,
        "mode": reading.get("mode", "unknown"),
        "frame_path": str(frame_path),
    }


def process_request(request):
    started = time.time()

    request_id = request.get("request_id")
    hand_token = request.get("hand_token")
    street = str(request.get("street") or "UNKNOWN").upper()

    seats = list(request.get("seats") or [])
    frames = list(request.get("frames") or [])

    observations = []

    # Boundary evidence must belong to the street that is ENDING.
    #
    # The request intentionally contains both the trailing old-street frames
    # and the first frame that proves the next street exists. Reading newest
    # first without filtering allowed the first FLOP frame to masquerade as
    # PREFLOP terminal evidence.
    #
    # Prefer the newest trusted OLD-STREET frame. Only if no trusted old-street
    # read exists do we fall back to the transition/new-street frames.
    expected_old_board_count = {
        "PREFLOP": 0,
        "FLOP": 3,
        "TURN": 4,
    }.get(street)

    old_street_frames = [
        item
        for item in frames
        if (
            expected_old_board_count is not None
            and item.get("local_board_count")
            == expected_old_board_count
        )
    ]

    transition_frames = [
        item
        for item in frames
        if item not in old_street_frames
    ]

    search_groups = (
        ("old_street", old_street_frames),
        ("transition_fallback", transition_frames),
    )

    for seat in seats:
        observation = None

        for evidence_scope, candidates in search_groups:
            for frame_item in reversed(candidates):
                frame_path = frame_item.get("frame_path")

                if not frame_path:
                    continue

                candidate = trusted_read(
                    frame_path,
                    seat,
                )

                if candidate is None:
                    continue

                candidate["frame_ts"] = (
                    frame_item.get("ts")
                )
                candidate["local_board_count"] = (
                    frame_item.get(
                        "local_board_count"
                    )
                )
                candidate["boundary_evidence_scope"] = (
                    evidence_scope
                )

                observation = candidate
                break

            if observation is not None:
                break

        observations.append({
            "seat": seat,
            "observation": observation,
        })

    return {
        "type": "boundary_stack_result",
        "request_id": request_id,
        "hand_token": hand_token,
        "street": street,
        "boundary_ts": request.get("boundary_ts"),
        "observations": observations,
        "elapsed_ms": round(
            (time.time() - started) * 1000.0,
            1,
        ),
        "ts": time.time(),
    }


def load_processed_ids():
    processed = set()

    if not RESULTS.exists():
        return processed

    for line in RESULTS.read_text().splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue

        request_id = item.get("request_id")

        if request_id:
            processed.add(request_id)

    return processed


def main():
    print(
        "api_boundary_stack_worker running. Ctrl+C to stop.",
        flush=True,
    )

    REQUESTS.parent.mkdir(parents=True, exist_ok=True)
    REQUESTS.touch(exist_ok=True)
    RESULTS.touch(exist_ok=True)

    processed = load_processed_ids()

    while True:
        try:
            lines = REQUESTS.read_text().splitlines()
        except Exception:
            time.sleep(0.05)
            continue

        did_work = False

        for line in lines:
            try:
                request = json.loads(line)
            except Exception:
                # Ignore partial JSONL writes.
                continue

            request_id = request.get("request_id")

            if not request_id or request_id in processed:
                continue

            result = process_request(request)

            append_jsonl(
                RESULTS,
                result,
            )

            processed.add(request_id)
            did_work = True

            print(
                "[BOUNDARY_STACK_WORKER]",
                f"request={request_id[:8]}",
                f"street={result.get('street')}",
                f"seats={len(result.get('observations') or [])}",
                f"elapsed={result.get('elapsed_ms')}ms",
                flush=True,
            )

        if not did_work:
            time.sleep(0.05)


if __name__ == "__main__":
    main()
