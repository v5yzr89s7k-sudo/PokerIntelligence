from pathlib import Path
import subprocess
import sys
import time
import signal

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime/live"
EVENT_LOG = LIVE / "api_events.jsonl"
STATE_CURSOR = LIVE / "api_event_state_machine_cursor.txt"

DRAIN_TIMEOUT_SECONDS = 10.0
DRAIN_POLL_SECONDS = 0.10

procs = []
stopping = False


def reset_runtime():
    LIVE.mkdir(parents=True, exist_ok=True)

    (LIVE / "api_events.jsonl").write_text("")
    (LIVE / "board_requests.jsonl").write_text("")
    (LIVE / "board_results.jsonl").write_text("")
    (LIVE / "hero_requests.jsonl").write_text("")
    (LIVE / "hero_results.jsonl").write_text("")
    (LIVE / "perception_latency.jsonl").write_text("")

    for name in [
        "api_event_state_machine_cursor.txt",
        "api_event_state_machine_state.json",
        "current_hand_state.json",
        "current_hand.txt",
        "api_event_coordinator_state.json",
        "current_action_episodes.json",
        "current_inferred_actions.json",
        "current_observation_timeline.json",
        "current_observation_correlator.json",
        "local_observations.jsonl",
        "canonical_hand.json",
        "current_hand_canonical.txt",
    ]:
        path = LIVE / name
        if path.exists():
            path.unlink()

    print("[RUNNER] reset live runtime", flush=True)


def start(name, args):
    print(f"[RUNNER] starting {name}", flush=True)
    process = subprocess.Popen(
        [sys.executable, *args],
        cwd=ROOT,
        start_new_session=True,
    )
    procs.append((name, process))


def get_process(name):
    for process_name, process in procs:
        if process_name == name:
            return process
    return None


def terminate_process(name, timeout=5.0):
    process = get_process(name)
    if process is None or process.poll() is not None:
        return

    print(f"[SHUTDOWN] stopping {name}", flush=True)
    process.terminate()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[SHUTDOWN] killing unresponsive {name}", flush=True)
        process.kill()
        process.wait()


def event_count():
    if not EVENT_LOG.exists():
        return 0

    with EVENT_LOG.open("r") as handle:
        return sum(1 for line in handle if line.strip())


def cursor_count():
    if not STATE_CURSOR.exists():
        return 0

    try:
        return int(STATE_CURSOR.read_text().strip() or "0")
    except (OSError, ValueError):
        return 0


def drain_state_machine():
    state_machine = get_process("state_machine")
    deadline = time.monotonic() + DRAIN_TIMEOUT_SECONDS
    last_report = None

    while True:
        cursor = cursor_count()
        total = event_count()

        if (cursor, total) != last_report:
            print(
                f"[SHUTDOWN] draining state machine: {cursor}/{total}",
                flush=True,
            )
            last_report = (cursor, total)

        if cursor >= total:
            print("[SHUTDOWN] event queue drained", flush=True)
            return True

        if state_machine is None or state_machine.poll() is not None:
            print(
                f"[SHUTDOWN] WARNING: state machine exited before drain "
                f"({cursor}/{total})",
                flush=True,
            )
            return False

        if time.monotonic() >= deadline:
            print(
                f"[SHUTDOWN] WARNING: drain timeout "
                f"({cursor}/{total} after {DRAIN_TIMEOUT_SECONDS:.0f}s)",
                flush=True,
            )
            return False

        time.sleep(DRAIN_POLL_SECONDS)


def stop_all(*_):
    global stopping

    if stopping:
        return

    stopping = True
    print("\n[SHUTDOWN] graceful shutdown requested", flush=True)

    # Stop every event producer before measuring the final queue length.
    terminate_process("coordinator")
    terminate_process("snapshot_worker")
    terminate_process("board_worker")
    terminate_process("hero_worker")

    # Leave the state machine alive until all durable events are consumed.
    drain_state_machine()
    terminate_process("state_machine")

    # Defensive cleanup for any process not covered above.
    for name, process in procs:
        if process.poll() is None:
            terminate_process(name)

    print("[SHUTDOWN] complete", flush=True)
    raise SystemExit(0)


signal.signal(signal.SIGINT, stop_all)
signal.signal(signal.SIGTERM, stop_all)

reset_runtime()
start("state_machine", ["src/api/api_event_state_machine.py"])
start("snapshot_worker", ["src/api/api_snapshot_worker.py"])
start("board_worker", ["src/api/api_board_worker.py"])
start("hero_worker", ["src/api/api_hero_worker.py"])
time.sleep(0.5)
start("coordinator", ["src/api/api_event_coordinator.py"])

while True:
    for name, process in procs:
        if process.poll() is not None:
            print(
                f"[RUNNER] {name} exited with code {process.returncode}",
                flush=True,
            )
            stop_all()
    time.sleep(1)
