from pathlib import Path
from time import perf_counter
import json
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.api.position_engine import assign_positions
from src.api.table_snapshot_reader_core_v2 import (
    read_table_snapshot_v2,
)


EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
CAPTURE_DIR = ROOT / "runtime/window_captures"


def latest_capture():
    files = sorted(
        CAPTURE_DIR.glob(
            "acr_table_*.png"
        )
    )
    return files[-1] if files else None


def emit(event):
    event["ts"] = time.time()

    with EVENT_LOG.open("a") as handle:
        handle.write(
            json.dumps(event) + "\n"
        )
        handle.flush()


def run_snapshot_v2(frame):
    started = perf_counter()

    try:
        snapshot, timings = (
            read_table_snapshot_v2(frame)
        )
    except Exception as exc:
        elapsed_ms = (
            perf_counter() - started
        ) * 1000.0

        print(
            "[SNAPSHOT_V2] reader failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "[PROFILE] SNAPSHOT_WORKER_V2 "
            f"total={elapsed_ms:.1f}ms "
            "failed=true",
            flush=True,
        )

        return None, elapsed_ms

    elapsed_ms = (
        perf_counter() - started
    ) * 1000.0

    print(
        "[PROFILE] SNAPSHOT_WORKER_V2 "
        f"total={elapsed_ms:.1f}ms "
        f"prepare={timings['prepare_ms']:.1f}ms "
        f"payload={timings['payload_ms']:.1f}ms "
        f"api={timings['api_ms']:.1f}ms "
        f"parse={timings['parse_ms']:.1f}ms "
        f"images={timings['image_count']} "
        f"seat_cards={timings['seat_card_count']} "
        f"image_kb={timings['image_bytes'] / 1024:.1f}",
        flush=True,
    )

    return snapshot, elapsed_ms


def process_event(
    event,
    processed_hero_events,
):
    if event.get("type") != "hero_cards":
        return

    event_ts = event.get("ts")
    event_key = str(event_ts)

    if event_key in processed_hero_events:
        return

    processed_hero_events.add(
        event_key
    )

    request_id = (
        event.get("source_request_id")
        or f"snapshot-v2-{event_key}"
    )
    hand_token = event.get(
        "hand_token"
    )

    log_latency(
        "trigger_consumed",
        request_id=request_id,
        worker="snapshot_v2",
        hand_token=hand_token,
        trigger_event="hero_cards",
        trigger_ts=event_ts,
    )

    frame = None

    frame_text = event.get("canonical_frame")

    if frame_text:
        candidate = Path(frame_text)
        if candidate.exists():
            frame = candidate

    if frame is None:
        frame = latest_capture()

    if frame is None:
        print(
            "[SNAPSHOT_V2] no captured frame available",
            flush=True,
        )
        return

    print(
        f"[SNAPSHOT_V2] reading from {frame.name}",
        flush=True,
    )

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="snapshot_v2",
        hand_token=hand_token,
        frame=str(frame),
    )

    snapshot, elapsed_ms = run_snapshot_v2(
        frame
    )

    if not snapshot:
        log_latency(
            "worker_finished",
            request_id=request_id,
            worker="snapshot_v2",
            hand_token=hand_token,
            ok=False,
            elapsed_ms=elapsed_ms,
        )
        return

    players = snapshot.get(
        "players"
    ) or []

    dealer_button_seat = (
        snapshot.get(
            "dealer_button_seat"
        )
        or ""
    )

    positions = assign_positions(
        players,
        dealer_button_seat,
    )

    hero_position = (
        positions.get("hero")
        or "unknown"
    )

    log_latency(
        "worker_finished",
        request_id=request_id,
        worker="snapshot_v2",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=elapsed_ms,
        player_count=len(players),
    )

    emit({
        "type": "table_snapshot_v2",
        "players": players,
        "occupied_seats": snapshot.get(
            "occupied_seats"
        ) or [],
        "dealer_button_seat": dealer_button_seat,
        "positions": positions,
        "hero_position": hero_position,
        "confidence": snapshot.get(
            "confidence"
        ),
        "source_request_id": request_id,
        "hand_token": hand_token,
    })

    log_latency(
        "event_emitted",
        request_id=request_id,
        worker="snapshot_v2",
        hand_token=hand_token,
        event_type="table_snapshot_v2",
        player_count=len(players),
    )

    print(
        "[SNAPSHOT_V2] emitted table_snapshot_v2",
        flush=True,
    )


def main():
    print(
        "api_snapshot_worker_v2 running. "
        "Ctrl+C to stop.",
        flush=True,
    )

    offset = 0
    processed_hero_events = set()

    while True:
        if not EVENT_LOG.exists():
            offset = 0
            time.sleep(0.1)
            continue

        size = EVENT_LOG.stat().st_size

        if size < offset:
            offset = 0
            processed_hero_events.clear()

        if size == offset:
            time.sleep(0.1)
            continue

        with EVENT_LOG.open("r") as handle:
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
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        "[SNAPSHOT_V2] ignored invalid event JSON",
                        flush=True,
                    )
                    continue

                process_event(
                    event,
                    processed_hero_events,
                )


if __name__ == "__main__":
    main()
