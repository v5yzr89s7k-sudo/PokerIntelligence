from pathlib import Path
from time import perf_counter
import json
import cv2
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import log as log_latency
from src.api.position_engine import assign_positions
from src.api.table_snapshot_reader_core_v2 import read_table_snapshot_v2
from src.api.canonical_frame import to_canonical_frame
from src.events.detectors.card_presence import hand_participant_presence

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
CAPTURE_DIR = ROOT / "runtime/window_captures"
SNAPSHOT_READER = ROOT / "src/api/table_snapshot_api_reader.py"


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    return files[-1] if files else None


def emit(event):
    event["ts"] = time.time()
    with EVENT_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")
        f.flush()


def run_snapshot(frame):
    t0 = perf_counter()

    try:
        snapshot, timings = read_table_snapshot_v2(
            frame,
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - t0) * 1000.0

        print(
            f"[SNAPSHOT] in-process reader failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            f"[PROFILE] SNAPSHOT_WORKER "
            f"total={elapsed_ms:.1f}ms failed=true",
            flush=True,
        )

        return None, elapsed_ms

    elapsed_ms = (perf_counter() - t0) * 1000.0

    print(
        f"[PROFILE] SNAPSHOT_WORKER "
        f"total={elapsed_ms:.1f}ms "
        f"prepare={timings['prepare_ms']:.1f}ms "
        f"payload={timings['payload_ms']:.1f}ms "
        f"api={timings['api_ms']:.1f}ms "
        f"parse={timings['parse_ms']:.1f}ms "
        f"images={timings['image_count']} "
        f"dealer={timings['dealer_ms']:.1f}ms "
        f"seat_cards={timings['seat_card_count']} "
        f"image_kb={timings['image_bytes'] / 1024:.1f}",
        flush=True,
    )

    return snapshot, elapsed_ms


def process_event(event, processed_hero_events):
    if event.get("type") != "hero_cards":
        return

    event_ts = event.get("ts")
    event_key = str(event_ts)

    if event_key in processed_hero_events:
        return

    processed_hero_events.add(event_key)

    request_id = event.get("source_request_id") or f"snapshot-{event_key}"
    hand_token = event.get("hand_token")

    log_latency(
        "trigger_consumed",
        request_id=request_id,
        worker="snapshot",
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
        else:
            print(
                f"[SNAPSHOT] canonical frame missing: {candidate}",
                flush=True,
            )

    if frame is None:
        print(
            "[SNAPSHOT] hero_cards event has no usable canonical frame",
            flush=True,
        )
        return

    print(f"[SNAPSHOT] reading from {frame.name}", flush=True)

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        frame=str(frame),
    )

    geometry = json.loads(
        (ROOT / "config/geometry.json").read_text()
    )

    original = cv2.imread(str(frame))

    if original is None or original.size == 0:
        print(
            f"[SNAPSHOT] could not read participant frame: {frame}",
            flush=True,
        )
        dealt_in_seats = []
    else:
        canonical = to_canonical_frame(
            original,
            geometry,
        )

        participant_state = hand_participant_presence(
            canonical,
            geometry,
            hero_is_dealt=True,
        )

        dealt_in_seats = [
            seat
            for seat, info in participant_state.items()
            if info.get("dealt_in")
        ]

    print(
        f"[PARTICIPANTS] count={len(dealt_in_seats)} "
        f"seats={dealt_in_seats}",
        flush=True,
    )

    snapshot, elapsed_ms = run_snapshot(frame)

    if snapshot:
        snapshot["dealt_in_seats"] = dealt_in_seats

    if not snapshot:
        log_latency(
            "worker_finished",
            request_id=request_id,
            worker="snapshot",
            hand_token=hand_token,
            ok=False,
            elapsed_ms=elapsed_ms,
        )
        return

    players = snapshot.get("players") or []

    dealt_in = set(
        snapshot.get("dealt_in_seats") or []
    )

    hand_players = [
        player
        for player in players
        if player.get("seat") in dealt_in
    ]

    dealer_button_seat = (
        snapshot.get("dealer_button_seat")
        or ""
    )

    positions = assign_positions(
        hand_players,
        dealer_button_seat,
    )

    print(
        f"[POSITIONS] seated={len(players)} "
        f"hand={len(hand_players)} "
        f"hero={positions.get('hero')}",
        flush=True,
    )

    hero_position = (
        positions.get("hero")
        or "unknown"
    )

    print("\n================ SNAPSHOT PLAYER DUMP ================", flush=True)
    for player in players:
        print(
            f"{player.get('seat'):18} "
            f"name={repr(player.get('name')):24} "
            f"stack={repr(player.get('stack_text')):12} "
            f"hero={player.get('is_hero')}",
            flush=True,
        )

    print(
        f"occupied_seats={snapshot.get('occupied_seats')}",
        flush=True,
    )
    print(
        f"dealt_in_seats={snapshot.get('dealt_in_seats')}",
        flush=True,
    )
    print(
        f"participant_count={len(snapshot.get('dealt_in_seats') or [])}",
        flush=True,
    )
    print(
        f"snapshot_count={len(players)}",
        flush=True,
    )
    print("=====================================================\n", flush=True)

    log_latency(
        "worker_finished",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=elapsed_ms,
        player_count=len(players),
    )

    emit({
        "type": "table_snapshot",
        "players": players,
        "dealt_in_seats": snapshot.get("dealt_in_seats", []),
        "dealer_button_seat": dealer_button_seat,
        "positions": positions,
        "hero_position": hero_position,
        "confidence": snapshot.get("confidence"),
        "source_request_id": request_id,
        "hand_token": hand_token,
    })

    log_latency(
        "event_emitted",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        event_type="table_snapshot",
        player_count=len(players),
    )

    print("[SNAPSHOT] emitted table_snapshot", flush=True)


def main():
    print("api_snapshot_worker running. Ctrl+C to stop.", flush=True)

    offset = 0
    processed_hero_events = set()

    while True:
        if not EVENT_LOG.exists():
            offset = 0
            time.sleep(0.1)
            continue

        size = EVENT_LOG.stat().st_size

        # Runner resets/truncates runtime files at startup.
        if size < offset:
            offset = 0
            processed_hero_events.clear()

        if size == offset:
            time.sleep(0.1)
            continue

        with EVENT_LOG.open("r") as f:
            f.seek(offset)

            while True:
                line_start = f.tell()
                line = f.readline()

                if not line:
                    break

                # Do not consume a partially written JSONL record.
                if not line.endswith("\n"):
                    f.seek(line_start)
                    break

                offset = f.tell()

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print("[SNAPSHOT] ignored invalid event JSON", flush=True)
                    continue

                process_event(event, processed_hero_events)


if __name__ == "__main__":
    main()
