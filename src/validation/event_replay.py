from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime" / "live"

EVENT_LOG = LIVE / "api_events.jsonl"
CURSOR = LIVE / "api_event_state_machine_cursor.txt"
STATE = LIVE / "api_event_state_machine_state.json"
CURRENT = LIVE / "current_hand.txt"

DRAIN_TIMEOUT_SECONDS = 10.0
POLL_SECONDS = 0.05


class EventReplayError(RuntimeError):
    pass


def _reset_state_machine_runtime():
    LIVE.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name in [
        "api_event_state_machine_cursor.txt",
        "api_event_state_machine_state.json",
        "current_hand_state.json",
        "current_hand.txt",
        "canonical_hand.json",
        "current_hand_canonical.txt",
        "last_completed_hand.txt",
        "last_completed_canonical_hand.json",
        "betting_round_status.json",
        "validation_summary.txt",
    ]:
        path = LIVE / name

        if path.exists():
            path.unlink()


def _event_count():
    if not EVENT_LOG.exists():
        return 0

    return sum(
        1
        for line in EVENT_LOG.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    )


def _cursor_count():
    if not CURSOR.exists():
        return 0

    try:
        return int(
            CURSOR.read_text(
                encoding="utf-8"
            ).strip()
            or "0"
        )
    except (OSError, ValueError):
        return 0


def replay(event_file: Path):
    event_file = Path(event_file)

    if not event_file.is_file():
        raise EventReplayError(
            f"event file does not exist: {event_file}"
        )

    _reset_state_machine_runtime()

    EVENT_LOG.write_text(
        event_file.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    total = _event_count()

    if total == 0:
        raise EventReplayError(
            f"event file is empty: {event_file}"
        )

    process = subprocess.Popen(
        [
            sys.executable,
            "src/api/api_event_state_machine.py",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        deadline = (
            time.monotonic()
            + DRAIN_TIMEOUT_SECONDS
        )

        while time.monotonic() < deadline:
            cursor = _cursor_count()

            if cursor >= total:
                break

            if process.poll() is not None:
                raise EventReplayError(
                    "state machine exited before event drain: "
                    f"{cursor}/{total}"
                )

            time.sleep(POLL_SECONDS)

        else:
            raise EventReplayError(
                "timed out draining event stream: "
                f"{_cursor_count()}/{total}"
            )

        if CURRENT.exists():
            return CURRENT.read_text(
                encoding="utf-8"
            )

        return ""

    finally:
        if process.poll() is None:
            process.terminate()

            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
