from pathlib import Path
from datetime import datetime
import fcntl
import os
import subprocess
import sys
import time
import signal
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime/live"
RUNNER_LOCK = LIVE / "run_live_observer.lock"
EVENT_LOG = LIVE / "api_events.jsonl"
STATE_CURSOR = LIVE / "api_event_state_machine_cursor.txt"
CURRENT_HAND = LIVE / "current_hand.txt"
DEBUG_LOG = LIVE / "observer_debug.log"
CURRENT_REPLAY_FRAME = LIVE / "current_replay_frame.json"
HAND_PROGRESSION_ROOT = ROOT / "runtime/debug/hand_progression"

SCK_SOURCE = ROOT / "src/capture/sck_sampler.swift"
SCK_BINARY = ROOT / "runtime/bin/poker_intelligence_sck_sampler"
SCK_SOCKET = Path("/tmp/poker_intelligence_frame.sock")

DRAIN_TIMEOUT_SECONDS = 10.0
DRAIN_POLL_SECONDS = 0.10
DISPLAY_POLL_SECONDS = 0.20

procs = []
stopping = False
debug_handle = None
last_displayed_content = None
terminal_display_active = False
hand_progression_sequence = 0


RUNTIME_PROCESS_MARKERS = (
    "src/api/api_event_coordinator.py",
    "src/api/api_event_state_machine.py",
    "src/api/api_snapshot_worker.py",
    "src/api/api_board_worker.py",
    "src/api/api_hero_worker.py",
    "src/api/api_pot_worker.py",
    "src/api/api_bet_amount_worker.py",
    "src/api/api_boundary_stack_worker.py",
    "src/api/api_stack_worker.py",
)


def find_orphan_runtime_processes():
    """
    Return Poker Intelligence runtime processes that are alive before this
    runner starts its own children.

    The flock prevents concurrent runners, but it cannot protect against
    orphan workers left behind after an abnormal runner death.
    """
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,command="],
        capture_output=True,
        text=True,
        check=True,
    )

    current_pid = os.getpid()
    matches = []

    for raw in result.stdout.splitlines():
        line = raw.strip()

        if not line:
            continue

        parts = line.split(None, 2)

        if len(parts) < 3:
            continue

        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue

        command = parts[2]

        if pid == current_pid:
            continue

        marker = next(
            (
                item
                for item in RUNTIME_PROCESS_MARKERS
                if item in command
            ),
            None,
        )

        if marker is None:
            continue

        matches.append({
            "pid": pid,
            "ppid": ppid,
            "command": command,
            "marker": marker,
        })

    return matches


def assert_clean_runtime_process_state():
    """
    Refuse startup if orphan runtime consumers already exist.

    This check intentionally occurs before reset_runtime(). Never truncate
    shared request/result files while stale consumers are still alive.
    """
    orphans = find_orphan_runtime_processes()

    if not orphans:
        return

    details = "\n".join(
        f"  pid={item['pid']} "
        f"ppid={item['ppid']} "
        f"{item['marker']}"
        for item in orphans
    )

    raise SystemExit(
        "Orphan Poker Intelligence runtime processes detected.\n"
        "Refusing to start because multiple consumers would corrupt "
        "request/result ordering.\n"
        f"{details}\n"
        "Stop the stale runtime processes before retrying."
    )


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
        "bet_amount_requests.jsonl",
        "bet_amount_results.jsonl",
        "boundary_stack_requests.jsonl",
        "boundary_stack_results.jsonl",
        "stack_requests.jsonl",
        "stack_results.jsonl",
        "perception_latency.jsonl",
        "observer_debug.log",
        "current_replay_frame.json",
        "replay_latency.jsonl",
        "coordinator_timing.jsonl",
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


def start_native(name, args, env=None):
    debug(f"starting {name}: {args}")

    process = subprocess.Popen(
        [str(arg) for arg in args],
        cwd=ROOT,
        stdout=debug_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
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


def build_sck_sampler():
    SCK_BINARY.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cmd = [
        "swiftc",
        "-parse-as-library",
        str(SCK_SOURCE),
        "-o",
        str(SCK_BINARY),
    ]

    debug(
        "compiling ScreenCaptureKit sampler: "
        + " ".join(cmd)
    )

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        stdout=debug_handle,
        stderr=subprocess.STDOUT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "ScreenCaptureKit sampler compilation failed; "
            f"see {DEBUG_LOG.relative_to(ROOT)}"
        )


def start_sck_sampler():
    try:
        SCK_SOCKET.unlink()
    except FileNotFoundError:
        pass

    build_sck_sampler()

    start_native(
        "sck_sampler",
        [SCK_BINARY],
    )

    deadline = time.monotonic() + 10.0

    while time.monotonic() < deadline:
        process = get_process(
            "sck_sampler"
        )

        if (
            process is None
            or process.poll() is not None
        ):
            raise RuntimeError(
                "ScreenCaptureKit sampler exited before "
                "creating its socket; "
                f"see {DEBUG_LOG.relative_to(ROOT)}"
            )

        if SCK_SOCKET.exists():
            debug(
                "ScreenCaptureKit sampler socket ready"
            )
            return

        time.sleep(0.05)

    raise RuntimeError(
        "timed out waiting for ScreenCaptureKit "
        f"socket {SCK_SOCKET}"
    )


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


def record_hand_progression(content):
    """
    Replay-debug audit trail.

    Every distinct current_hand.txt version is paired with the most recently
    released replay frame. Normal live observation is intentionally untouched.
    """
    global hand_progression_sequence

    replay_session = os.environ.get(
        "POKER_REPLAY_SESSION"
    )

    if not replay_session:
        return

    if not content:
        return

    if not CURRENT_REPLAY_FRAME.exists():
        return

    try:
        frame_state = json.loads(
            CURRENT_REPLAY_FRAME.read_text(
                encoding="utf-8"
            )
        )

        frame_number = int(
            frame_state["frame"]
        )

        frame_path = Path(
            frame_state["frame_path"]
        )

        if not frame_path.exists():
            debug(
                "hand progression frame missing: "
                f"{frame_path}"
            )
            return

        session_name = (
            Path(replay_session).name
            or "replay"
        )

        out = (
            HAND_PROGRESSION_ROOT
            / session_name
        )

        out.mkdir(
            parents=True,
            exist_ok=True,
        )

        hand_progression_sequence += 1
        sequence = hand_progression_sequence

        stem = (
            f"{sequence:03d}_"
            f"frame_{frame_number:04d}"
        )

        image_destination = (
            out / f"{stem}.png"
        )

        text_destination = (
            out / f"{stem}_current_hand.txt"
        )

        metadata_destination = (
            out / f"{stem}_meta.json"
        )

        shutil.copy2(
            frame_path,
            image_destination,
        )

        text_destination.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
        )

        metadata = {
            "sequence": sequence,
            "frame": frame_number,
            "source_frame": str(
                frame_path
            ),
            "image": image_destination.name,
            "current_hand": (
                text_destination.name
            ),
            "captured_at": (
                datetime.now().isoformat()
            ),
            **frame_state,
        }

        metadata_destination.write_text(
            json.dumps(
                metadata,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        debug(
            "[HAND_PROGRESSION] "
            f"sequence={sequence:03d} "
            f"frame={frame_number:04d} "
            f"text={text_destination.name}"
        )

    except Exception as exc:
        debug(
            "could not record hand progression: "
            f"{exc}"
        )


def render_live_display(force=False):
    global last_displayed_content

    content = read_current_hand()

    if not force and content == last_displayed_content:
        return

    last_displayed_content = content

    if not force:
        record_hand_progression(content)

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
    terminate_process("sck_sampler")
    terminate_process("snapshot_worker")
    terminate_process("board_worker")
    terminate_process("hero_worker")
    terminate_process("pot_worker")
    terminate_process("bet_amount_worker")
    terminate_process("boundary_stack_worker")
    terminate_process("stack_worker")

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

# flock prevents a second runner, but orphan workers can outlive a runner
# after abnormal termination. Detect them before truncating shared runtime
# files or starting another set of consumers.
assert_clean_runtime_process_state()

reset_runtime()
open_debug_log()

start("state_machine", ["src/api/api_event_state_machine.py"])
start("snapshot_worker", ["src/api/api_snapshot_worker.py"])
start("board_worker", ["src/api/api_board_worker.py"])
start("hero_worker", ["src/api/api_hero_worker.py"])
start("pot_worker", ["src/api/api_pot_worker.py"])
start(
    "bet_amount_worker",
    ["src/api/api_bet_amount_worker.py"],
)
start(
    "boundary_stack_worker",
    ["src/api/api_boundary_stack_worker.py"],
)
start(
    "stack_worker",
    ["src/api/api_stack_worker.py"],
)

time.sleep(0.5)

replay_mode = bool(
    os.environ.get(
        "POKER_REPLAY_SESSION"
    )
)

if replay_mode:
    debug(
        "replay mode: ScreenCaptureKit sampler disabled"
    )

    os.environ.pop(
        "POKER_SCK_CAPTURE",
        None,
    )

else:
    debug(
        "live mode: enabling ScreenCaptureKit acquisition"
    )

    start_sck_sampler()

    os.environ[
        "POKER_SCK_CAPTURE"
    ] = "1"

start(
    "coordinator",
    ["src/api/api_event_coordinator.py"],
)

enter_live_display()
render_live_display(force=True)

while True:
    for name, process in procs:
        if process.poll() is not None:
            debug(
                f"{name} exited with code "
                f"{process.returncode}"
            )

            # In replay mode the coordinator owns replay EOF. A clean
            # coordinator exit means all already-published asynchronous
            # transport has settled and no more perception frames will arrive.
            # Reuse the ordinary graceful shutdown path so producers stop
            # before the state machine performs its final durable event drain.
            if (
                replay_mode
                and name == "coordinator"
                and process.returncode == 0
            ):
                debug(
                    "replay coordinator completed cleanly; "
                    "starting runner shutdown"
                )
                stop_all()
                continue

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
