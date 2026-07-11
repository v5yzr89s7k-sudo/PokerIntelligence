from pathlib import Path
from time import perf_counter
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

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

    p = subprocess.run(
        ["python3", str(SNAPSHOT_READER), str(frame)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    elapsed_ms = (perf_counter() - t0) * 1000.0
    print(f"[PROFILE] SNAPSHOT_WORKER {elapsed_ms:.1f} ms", flush=True)

    if p.returncode != 0:
        print("[SNAPSHOT] reader failed", flush=True)
        if p.stderr.strip():
            print(p.stderr.strip(), flush=True)
        return None

    text = p.stdout.strip()

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        print("[SNAPSHOT] could not parse reader JSON", flush=True)
        if text:
            print(text, flush=True)
        return None


def process_event(event, processed_hero_events):
    if event.get("type") != "hero_cards":
        return

    event_ts = event.get("ts")
    event_key = str(event_ts)

    if event_key in processed_hero_events:
        return

    processed_hero_events.add(event_key)

    frame = latest_capture()
    if frame is None:
        print("[SNAPSHOT] no captured frame available", flush=True)
        return

    print(f"[SNAPSHOT] reading from {frame.name}", flush=True)
    snapshot = run_snapshot(frame)

    if not snapshot:
        return

    emit({
        "type": "table_snapshot",
        "players": snapshot.get("players") or [],
        "hero_position": snapshot.get("hero_position") or "unknown",
        "dealer_button_seat": snapshot.get("dealer_button_seat") or "",
        "confidence": snapshot.get("confidence"),
    })

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
