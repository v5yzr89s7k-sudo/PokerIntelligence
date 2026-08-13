from pathlib import Path
from datetime import datetime
import fcntl
import os
import subprocess
import sys
import time
import signal

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime/live"
RUNNER_LOCK = LIVE / "run_live_observer.lock"
EVENT_LOG = LIVE / "api_events.jsonl"
STATE_CURSOR = LIVE / "api_event_state_machine_cursor.txt"
CURRENT_HAND = LIVE / "current_hand.txt"
DEBUG_LOG = LIVE / "observer_debug.log"

DRAIN_TIMEOUT_SECONDS = 10.0
DRAIN_POLL_SECONDS = 0.10
DISPLAY_POLL_SECONDS = 0.20

procs = []
stopping = False
debug_handle = None
last_displayed_content = None
terminal_display_active = False


def acquire_single_instance():
    LIVE.mkdir(parents=True, exist_ok=True)

    lock_handle = RUNNER_LOCK.open(
        "a+",
        encoding="utf-8",
    )

    try:
        fcntl.flock(
            lock_handle.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )
    except BlockingIOError:
        lock_handle.close()
        raise SystemExit(
            "Poker Intelligence observer is already running. "
            "Refusing to start a second instance."
        )

    lock_handle.seek(0)
    lock_handle.truncate()
    lock_handle.write(str(os.getpid()) + "\n")
    lock_handle.flush()

    return lock_handle


def reset_runtime():
    LIVE.mkdir(parents=True, exist_ok=True)

    for name in [
        "api_events.jsonl",
        "board_requests.jsonl",
        "board_results.jsonl",
        "hero_requests.jsonl",
        "hero_results.jsonl",
        "pot_requests.jsonl",
        "pot_results.jsonl",
        "boundary_stack_requests.jsonl",
        "boundary_stack_results.jsonl",
        "perception_latency.jsonl",
        "observer_debug.log",
    ]:
        (LIVE / name).write_text("")

    (LIVE / "participant_evidence.json").write_text("{}\n")

    for name in [
        "api_event_state_machine_cursor.txt",
        "api_event_state_machine_state.json",
        "current_hand_state.json",
        "current_hand.txt",
        "api_event_coordinator_state.json",
        "current_action_episodes.json",
        "current_inferred_actions.json",
        "pending_episode_scheduler.json",
        "current_observation_timeline.json",
        "current_observation_correlator.json",
        "local_observations.jsonl",
        "canonical_hand.json",
        "current_hand_canonical.txt",
        "last_completed_hand.txt",
        "last_completed_canonical_hand.json",
        "validation_summary.txt",
        "betting_round_status.json",
        "boundary_stack_state_machine_cursor.txt",
    ]:
        runtime_path = LIVE / name
        if runtime_path.exists():
            runtime_path.unlink()


def open_debug_log():
    global debug_handle

    debug_handle = DEBUG_LOG.open(
        "a",
        buffering=1,
        encoding="utf-8",
    )

    debug_handle.write(
        "\n"
        "============================================================\n"
        f"Poker Intelligence observer started: {datetime.now().isoformat()}\n"
        "============================================================\n"
    )


def debug(message):
    if debug_handle is None:
        return

    debug_handle.write(f"[RUNNER] {message}\n")


def start(name, args):
    debug(f"starting {name}: {args}")

    process = subprocess.Popen(
        [sys.executable, *args],
        cwd=ROOT,
        stdout=debug_handle,
        stderr=subprocess.STDOUT,
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

    debug(f"stopping {name}")
    process.terminate()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        debug(f"killing unresponsive {name}")
        process.kill()
        process.wait()


def event_count():
    if not EVENT_LOG.exists():
        return 0

    with EVENT_LOG.open("r", encoding="utf-8") as handle:
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
            debug(f"draining state machine: {cursor}/{total}")
            last_report = (cursor, total)

        if cursor >= total:
            debug("event queue drained")
            return True

        if state_machine is None or state_machine.poll() is not None:
            debug(
                "WARNING: state machine exited before drain "
                f"({cursor}/{total})"
            )
            return False

        if time.monotonic() >= deadline:
            debug(
                "WARNING: drain timeout "
                f"({cursor}/{total} after {DRAIN_TIMEOUT_SECONDS:.0f}s)"
            )
            return False

        time.sleep(DRAIN_POLL_SECONDS)


def enter_live_display():
    global terminal_display_active

    if terminal_display_active:
        return

    # Use the terminal's alternate screen buffer so live redraws do not
    # accumulate in normal scrollback or appear as duplicated hand snapshots.
    sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
    sys.stdout.flush()
    terminal_display_active = True


def exit_live_display():
    global terminal_display_active

    if not terminal_display_active:
        return

    sys.stdout.write("\033[?25h\033[?1049l")
    sys.stdout.flush()
    terminal_display_active = False


def clear_terminal():
    # Redraw one persistent screen in place.
    sys.stdout.write("\033[H\033[J")


def read_current_hand():
    try:
        if not CURRENT_HAND.exists():
            return ""

        return CURRENT_HAND.read_text(encoding="utf-8").rstrip()
    except OSError as exc:
        debug(f"could not read current_hand.txt: {exc}")
        return ""


def render_live_display(force=False):
    global last_displayed_content

    content = read_current_hand()

    if not force and content == last_displayed_content:
        return

    last_displayed_content = content

    clear_terminal()

    print("=" * 64)
    print("POKER INTELLIGENCE — LIVE HAND")
    print(
        "Updated:",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    print("=" * 64)
    print()

    if content:
        print(content)
    else:
        print("Waiting for a hand...")
        print()
        print("The ACR table may now be opened or brought into view.")

    print()
    print("-" * 64)
    print("Ctrl+C to stop")
    print(f"Diagnostics: {DEBUG_LOG.relative_to(ROOT)}")
    sys.stdout.flush()


def close_debug_log():
    global debug_handle

    if debug_handle is None:
        return

    try:
        debug_handle.flush()
        debug_handle.close()
    finally:
        debug_handle = None


def stop_all(*_):
    global stopping

    if stopping:
        return

    stopping = True
    debug("graceful shutdown requested")

    # Stop all event producers before measuring the final queue length.
    terminate_process("coordinator")
    terminate_process("snapshot_worker")
    terminate_process("board_worker")
    terminate_process("hero_worker")
    terminate_process("pot_worker")
    terminate_process("boundary_stack_worker")

    # Leave the state machine alive until all durable events are consumed.
    drain_state_machine()
    terminate_process("state_machine")

    # Defensive cleanup for any process not covered above.
    for name, process in procs:
        if process.poll() is None:
            terminate_process(name)

    debug("shutdown complete")
    close_debug_log()

    exit_live_display()

    # Preserve the final canonical hand in normal terminal scrollback after
    # leaving the alternate live-display buffer.
    try:
        final_content = CURRENT_HAND.read_text()
    except Exception:
        final_content = ""

    if final_content.strip():
        print(final_content.rstrip())
        print()

    print("Observer stopped cleanly.")
    raise SystemExit(0)


signal.signal(signal.SIGINT, stop_all)
signal.signal(signal.SIGTERM, stop_all)

single_instance_lock = acquire_single_instance()

reset_runtime()
open_debug_log()

start("state_machine", ["src/api/api_event_state_machine.py"])
start("snapshot_worker", ["src/api/api_snapshot_worker.py"])
start("board_worker", ["src/api/api_board_worker.py"])
start("hero_worker", ["src/api/api_hero_worker.py"])
start("pot_worker", ["src/api/api_pot_worker.py"])
start(
    "boundary_stack_worker",
    ["src/api/api_boundary_stack_worker.py"],
)

time.sleep(0.5)

start("coordinator", ["src/api/api_event_coordinator.py"])

enter_live_display()
render_live_display(force=True)

while True:
    for name, process in procs:
        if process.poll() is not None:
            debug(f"{name} exited with code {process.returncode}")

            clear_terminal()
            print("=" * 64)
            print("POKER INTELLIGENCE — PROCESS FAILURE")
            print("=" * 64)
            print()
            print(f"{name} exited with code {process.returncode}.")
            print(f"See: {DEBUG_LOG.relative_to(ROOT)}")
            print()
            sys.stdout.flush()

            stop_all()

    render_live_display()
    time.sleep(DISPLAY_POLL_SECONDS)
