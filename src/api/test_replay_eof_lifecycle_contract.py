from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

COORDINATOR = ROOT / "src/api/api_event_coordinator.py"
RUNNER = ROOT / "src/api/run_live_observer.py"


def function_source(text, name):
    tree = ast.parse(text)
    lines = text.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(
                lines[node.lineno - 1:node.end_lineno]
            )

    raise AssertionError(
        f"function not found: {name}"
    )


def main():
    coordinator = COORDINATOR.read_text()
    runner = RUNNER.read_text()

    helper = function_source(
        coordinator,
        "replay_outstanding_transport",
    )

    coordinator_main = function_source(
        coordinator,
        "main",
    )

    required_helper = [
        'state.get("hero_request_id")',
        'state.get("board_request_id")',
        'state.get("pot_request_id")',
        'state.get("pending_bet_amount_requests")',
        'state.get("pending_stack_worker_requests")',
    ]

    missing = [
        item
        for item in required_helper
        if item not in helper
    ]

    assert not missing, (
        f"missing replay transport blockers: {missing}"
    )

    forbidden_helper = [
        'state.get("pending_startup_stack_seats")',
    ]

    present = [
        item
        for item in forbidden_helper
        if item in helper
    ]

    assert not present, (
        f"non-transport state incorrectly blocks EOF: {present}"
    )

    required_main = [
        "if replay is not None and replay.exhausted:",
        "consume_ready_worker_results(state)",
        "replay_outstanding_transport(",
        "replay_pending_stack_candidates(",
        "drain_replay_stack_candidates_once(",
        "[REPLAY_EOF]",
        "[REPLAY_DRAIN]",
        "[REPLAY_COMPLETE]",
    ]

    missing = [
        item
        for item in required_main
        if item not in coordinator_main
    ]

    assert not missing, (
        f"missing coordinator EOF behavior: {missing}"
    )

    clean_marker = 'and name == "coordinator"'

    assert clean_marker in runner, (
        "runner has no clean replay coordinator branch"
    )

    start = runner.index(clean_marker)

    failure = runner.index(
        'print("POKER INTELLIGENCE — PROCESS FAILURE")',
        start,
    )

    clean_region = runner[start:failure]

    assert "process.returncode == 0" in clean_region
    assert "stop_all()" in clean_region
    assert "continue" in clean_region

    print(
        "PASS replay EOF lifecycle contract: "
        "EOF freezes perception, drains published transport, "
        "and clean coordinator completion cannot enter failure handling"
    )


if __name__ == "__main__":
    main()
