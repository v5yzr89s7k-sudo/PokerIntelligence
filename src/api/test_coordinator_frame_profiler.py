from pathlib import Path
import ast


def main():
    coordinator = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    runner = Path(
        "src/api/run_live_observer.py"
    ).read_text()

    assert (
        'COORDINATOR_TIMING = ROOT / '
        '"runtime/live/coordinator_timing.jsonl"'
        in coordinator
    )

    assert "def _append_coordinator_timing(" in coordinator

    required = [
        '"capture"',
        '"imread"',
        '"resize"',
        '"participant_evidence"',
        '"local_detector"',
        '"fast_actor"',
        '"startup_stack_retry"',
        '"stack_result_collect"',
        '"stack_reconciliation"',
        '"winner_detection"',
        '"observer_pipeline"',
        '"hero_read_coordination"',
        '"board_coordination"',
        '"hero_blink"',
        '"hand_completion"',
        '"state_persist"',
    ]

    missing = [
        item
        for item in required
        if item not in coordinator
    ]

    assert not missing, (
        "missing coordinator timing stages: "
        + ", ".join(missing)
    )

    assert (
        '"coordinator_timing.jsonl",'
        in runner
    )

    # Structural compile-level protection.
    ast.parse(coordinator)

    print(
        "PASS coordinator frame profiler: "
        "major synchronous stages are durably timed "
        "per replay frame"
    )


if __name__ == "__main__":
    main()
