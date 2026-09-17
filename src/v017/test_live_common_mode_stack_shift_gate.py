"""
V0.17 live common-mode pre-settlement structural contract.

FrameHandObserver remains perception-only.

The production runner must:
1. classify the complete same-frame quantitative batch;
2. expose only eligible quantitative observations to settlement;
3. retain explicit observability for rejected common-mode evidence;
4. perform all rejection before StackSettlementGate.observe().
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "src/v017/run_live_observer.py"
)

OBSERVER = (
    ROOT
    / "src/v017/frame_hand_observer.py"
)


def function_source(source, tree, name):
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        ):
            return ast.get_source_segment(
                source,
                node,
            )

    raise AssertionError(
        f"missing function: {name}"
    )


def main():
    runner_source = RUNNER.read_text()
    runner_tree = ast.parse(runner_source)

    observer_source = OBSERVER.read_text()

    run = function_source(
        runner_source,
        runner_tree,
        "run_hand",
    )

    transaction = function_source(
        runner_source,
        runner_tree,
        "filter_common_mode_quantitative_events",
    )

    # Classifier primitive remains perception-independent.
    assert (
        "def common_mode_stack_shift_seats("
        in observer_source
    )

    # Extracted production transaction owns frame-level filtering.
    assert (
        "common_mode_stack_shift_seats("
        in transaction
    )

    assert (
        '"STACK_QUANTITATIVE_OBSERVATION"'
        in transaction
    )

    assert (
        "eligible"
        in transaction
    )

    assert (
        "rejected"
        in transaction
    )

    # run_hand must invoke the complete-frame transaction before
    # entering settlement ownership.
    filter_index = run.find(
        "filter_common_mode_quantitative_events("
    )

    settlement_index = run.find(
        "settlement_gate.observe("
    )

    assert filter_index >= 0
    assert settlement_index >= 0

    assert filter_index < settlement_index, (
        "MISSING PRE-SETTLEMENT GATE: frame-level "
        "common-mode filtering occurs after settlement"
    )

    # Explicit rejected-seat ownership must be established from the
    # transaction result.
    assert (
        "common_mode_quantitative_events"
        in run
    )

    assert (
        "common_mode_seats"
        in run
    )

    # Rejected evidence remains observable and must short-circuit
    # before StackSettlementGate.observe().
    reject_index = run.find(
        "[COMMON_MODE_STACK_SHIFT_REJECTED]"
    )

    assert reject_index >= 0

    assert reject_index < settlement_index, (
        "COMMON-MODE REJECTION OCCURS AFTER SETTLEMENT"
    )

    reject_region = run[
        reject_index:
        settlement_index
    ]

    assert "continue" in reject_region, (
        "COMMON-MODE REJECTION DOES NOT SHORT-CIRCUIT "
        "SETTLEMENT OWNERSHIP"
    )

    # Raw quantitative observations remain visible to the runner.
    assert (
        '"STACK_QUANTITATIVE_OBSERVATION"'
        in run
    )

    print(
        "V0.17 LIVE COMMON-MODE STACK SHIFT GATE: PASS"
    )


if __name__ == "__main__":
    main()
