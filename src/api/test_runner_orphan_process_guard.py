from pathlib import Path
import ast


RUNNER = Path(
    "src/api/run_live_observer.py"
)


def main():
    text = RUNNER.read_text()
    tree = ast.parse(text)

    assert (
        "def find_orphan_runtime_processes():"
        in text
    )

    assert (
        "def assert_clean_runtime_process_state():"
        in text
    )

    assert (
        "RUNTIME_PROCESS_MARKERS = ("
        in text
    )

    # All normal long-lived Python runtime consumers must be guarded.
    required_markers = [
        "api_event_coordinator.py",
        "api_event_state_machine.py",
        "api_snapshot_worker.py",
        "api_board_worker.py",
        "api_hero_worker.py",
        "api_pot_worker.py",
        "api_bet_amount_worker.py",
        "api_boundary_stack_worker.py",
        "api_stack_worker.py",
    ]

    for marker in required_markers:
        assert marker in text, marker

    lock_pos = text.index(
        "single_instance_lock = acquire_single_instance()"
    )

    guard_pos = text.index(
        "assert_clean_runtime_process_state()",
        lock_pos,
    )

    reset_pos = text.index(
        "reset_runtime()",
        lock_pos,
    )

    first_start_pos = text.index(
        'start("state_machine"',
        lock_pos,
    )

    assert (
        lock_pos
        < guard_pos
        < reset_pos
        < first_start_pos
    ), (
        lock_pos,
        guard_pos,
        reset_pos,
        first_start_pos,
    )

    print(
        "PASS runner orphan-process guard: "
        "single-instance lock is followed by stale-consumer detection "
        "before runtime reset or worker startup"
    )


if __name__ == "__main__":
    main()
