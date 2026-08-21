from pathlib import Path
from datetime import datetime
import json
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime" / "live"
CAPTURE_SCRIPT = ROOT / "src" / "vision" / "window_capture.py"
CAPTURE_DIR = ROOT / "runtime" / "window_captures"
GOLDEN_ROOT = ROOT / "runtime" / "golden_hands"

CURRENT_HAND = LIVE / "current_hand.txt"
EVENT_LOG = LIVE / "api_events.jsonl"


def next_hand_dir():
    GOLDEN_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    numbers = []

    for path in GOLDEN_ROOT.glob("hand_*"):
        try:
            numbers.append(
                int(path.name.split("_", 1)[1])
            )
        except (IndexError, ValueError):
            pass

    number = max(numbers, default=0) + 1

    return (
        GOLDEN_ROOT / f"hand_{number:04d}",
        number,
    )


def capture_frame(destination):
    subprocess.run(
        [
            sys.executable,
            str(CAPTURE_SCRIPT),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    captures = sorted(
        CAPTURE_DIR.glob("acr_table_*.png")
    )

    if not captures:
        raise RuntimeError(
            "window capture produced no frame"
        )

    shutil.copyfile(
        captures[-1],
        destination,
    )


def main():
    hand_dir, number = next_hand_dir()
    frames_dir = hand_dir / "frames"

    hand_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    frames_dir.mkdir()

    started = datetime.now()

    print("=" * 64)
    print("POKER INTELLIGENCE — GOLDEN HAND RECORDER")
    print("=" * 64)
    print()
    print(f"Fixture: {hand_dir.relative_to(ROOT)}")
    print()
    print("IMPORTANT:")
    print("  1. The normal live observer must already be running.")
    print("  2. Start this BEFORE the target hand is dealt.")
    print("  3. DO NOT press Ctrl+C.")
    print("  4. Recording stops automatically after hand_complete.")
    print()
    print("Recording...")
    print()

    event_start_line = 0

    if EVENT_LOG.exists():
        event_start_line = sum(
            1
            for line in EVENT_LOG.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        )

    frame_number = 1

    try:
        while True:
            destination = (
                frames_dir
                / f"frame_{frame_number:05d}.png"
            )

            capture_frame(destination)

            if frame_number % 10 == 0:
                print(
                    f"Captured {frame_number} frames",
                    flush=True,
                )

            frame_number += 1
            time.sleep(0.15)

            if EVENT_LOG.exists():
                live_event_lines = [
                    line
                    for line in EVENT_LOG.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if line.strip()
                ]

                recording_lines = live_event_lines[
                    event_start_line:
                ]

                target_hand_started = False
                target_hand_complete = False

                for line in recording_lines:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    # Events arriving after recorder start may still belong to
                    # the previous hand because workers are asynchronous.
                    # The target fixture begins only at the first hero_cards.
                    if not target_hand_started:
                        if event_type == "hero_cards":
                            target_hand_started = True
                        continue

                    if event_type == "hand_complete":
                        target_hand_complete = True
                        break

                if target_hand_complete:
                    print()
                    print(
                        "Target hand complete detected. "
                        "Stopping recording automatically."
                    )

                    # Give the state machine a short window to finish
                    # publishing current_hand.txt for this terminal event.
                    time.sleep(0.75)
                    break

    except KeyboardInterrupt:
        pass

    frame_count = frame_number - 1

    if frame_count == 0:
        shutil.rmtree(hand_dir)
        raise SystemExit(
            "No frames captured; fixture removed."
        )

    if not CURRENT_HAND.exists():
        print()
        print(
            "ERROR: runtime/live/current_hand.txt "
            "does not exist."
        )
        print(
            "Invalid fixture removed."
        )
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    expected = CURRENT_HAND.read_text(
        encoding="utf-8"
    )

    if not expected.strip():
        print()
        print(
            "ERROR: current_hand.txt is empty."
        )
        print(
            "Invalid fixture removed."
        )
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    expected_path = (
        hand_dir
        / "expected_current_hand.txt"
    )

    expected_path.write_text(
        expected,
        encoding="utf-8",
    )

    if not EVENT_LOG.exists():
        print()
        print(
            "ERROR: runtime/live/api_events.jsonl "
            "does not exist."
        )
        print(
            "Invalid fixture removed."
        )
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    all_event_lines = [
        line
        for line in EVENT_LOG.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    raw_recording_lines = all_event_lines[
        event_start_line:
    ]

    # A recorder may begin while late asynchronous events from the previous
    # hand are still arriving. Define the golden fixture semantically:
    #
    #   first hero_cards
    #       through
    #   first hand_complete
    #
    # Nothing outside that interval belongs to the target hand.
    recording_event_lines = []
    target_hand_started = False
    target_hand_complete = False

    for line in raw_recording_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")

        if not target_hand_started:
            if event_type != "hero_cards":
                continue

            target_hand_started = True

        recording_event_lines.append(line)

        if event_type == "hand_complete":
            target_hand_complete = True
            break

    events_text = (
        "\n".join(recording_event_lines)
        + ("\n" if recording_event_lines else "")
    )

    if not target_hand_started:
        print()
        print(
            "ERROR: target hand never produced hero_cards."
        )
        print("Invalid fixture removed.")
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    if not target_hand_complete:
        print()
        print(
            "ERROR: target hand never completed."
        )
        print("Invalid fixture removed.")
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    if not events_text.strip():
        print()
        print(
            "ERROR: no api events were produced "
            "during this recording."
        )
        print(
            "Invalid fixture removed."
        )
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    hand_complete_count = 0

    for line in recording_event_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "hand_complete":
            hand_complete_count += 1

    if hand_complete_count != 1:
        print()
        print(
            "ERROR: recording must contain exactly "
            "one completed hand."
        )
        print(
            f"hand_complete events: "
            f"{hand_complete_count}"
        )
        print(
            "Invalid fixture removed."
        )
        shutil.rmtree(
            hand_dir,
            ignore_errors=True,
        )
        return 1

    events_path = (
        hand_dir
        / "api_events.jsonl"
    )

    events_path.write_text(
        events_text,
        encoding="utf-8",
    )

    metadata = {
        # Format v2 records the chronology-aware event-stream era.
        # Existing v1 fixtures remain immutable historical evidence.
        "format_version": 2,
        "hand_number": number,
        "recorded_at": started.isoformat(),
        "completed_at": datetime.now().isoformat(),
        "frame_count": frame_count,
        "event_count": sum(
            1
            for line in events_text.splitlines()
            if line.strip()
        ),
        "expected_source": (
            "runtime/live/current_hand.txt"
        ),
        "events_source": (
            "runtime/live/api_events.jsonl"
        ),
        "allow_live_workers": False,
        "status": "candidate",
    }

    (
        hand_dir / "metadata.json"
    ).write_text(
        json.dumps(
            metadata,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 64)
    print("CANDIDATE GOLDEN HAND RECORDED")
    print("=" * 64)
    print(f"Frames : {frame_count}")
    print(
        "Output : "
        f"{expected_path.relative_to(ROOT)}"
    )
    print(
        "Events : "
        f"{events_path.relative_to(ROOT)}"
    )
    print()
    print(
        "Status is CANDIDATE until the expected "
        "hand is manually verified."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
