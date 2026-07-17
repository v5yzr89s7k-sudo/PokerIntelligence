from pathlib import Path
import subprocess
import sys
import time
import signal

ROOT = Path(__file__).resolve().parents[2]

procs = []

def reset_runtime():
    live = ROOT / "runtime/live"
    live.mkdir(parents=True, exist_ok=True)

    (live / "api_events.jsonl").write_text("")
    (live / "board_requests.jsonl").write_text("")
    (live / "board_results.jsonl").write_text("")
    (live / "hero_requests.jsonl").write_text("")
    (live / "hero_results.jsonl").write_text("")
    (live / "perception_latency.jsonl").write_text("")

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
        path = live / name
        if path.exists():
            path.unlink()

    print("[RUNNER] reset live runtime")


def start(name, args):
    print(f"[RUNNER] starting {name}")
    p = subprocess.Popen([sys.executable, *args], cwd=ROOT)
    procs.append((name, p))

def stop_all(*_):
    print("\n[RUNNER] stopping")
    for name, p in procs:
        if p.poll() is None:
            print(f"[RUNNER] stopping {name}")
            p.terminate()
    for name, p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    sys.exit(0)

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
    for name, p in procs:
        if p.poll() is not None:
            print(f"[RUNNER] {name} exited with code {p.returncode}")
            stop_all()
    time.sleep(1)
