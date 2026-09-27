"""
Structural safety contract for the v0.17 live runner.

run_hand owns acquisition/timing only.

process_frame_transaction owns quantitative settlement and semantic
admission.

Raw quantitative OCR may mutate HandEngine only through:

    STACK_QUANTITATIVE_OBSERVATION
        -> StackSettlementGate.observe()
        -> non-None settlement
        -> admit_quantitative_observation()

One FrameTransactionState belongs to one physical hand and owns one
StackSettlementGate.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "src/v017/run_live_observer.py"


def get_function(source, tree, name):
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
    source = RUNNER.read_text()
    tree = ast.parse(source)

    run = get_function(
        source,
        tree,
        "run_hand",
    )

    transaction = get_function(
        source,
        tree,
        "process_frame_transaction",
    )

    assert (
        "state = FrameTransactionState()"
        in run
    )

    assert (
        "self.settlement_gate = "
        "StackSettlementGate()"
        in source
    )

    assert (
        '"STACK_QUANTITATIVE_OBSERVATION"'
        in transaction
    )

    assert (
        "[QUANTITATIVE_DEFERRED]"
        in transaction
    )

    settle = transaction.index(
        "state.settlement_gate.observe("
    )

    admission = transaction.index(
        "admit_quantitative_observation"
    )

    assert settle < admission

    settled_branch = transaction[
        settle:
        admission + 200
    ]

    assert (
        "if settled is None:"
        in settled_branch
    )

    assert (
        "else:"
        in settled_branch
    )

    forbidden = (
        ".observe_stack_commitment(",
        ".trusted_stacks[",
        "hand.observe_stack_commitment(",
    )

    for token in forbidden:
        assert token not in run, (
            "live acquisition loop bypasses "
            "semantic boundary: "
            f"{token}"
        )

    assert (
        "HERO_CARDS_DISAPPEARED_PHYSICAL"
        in transaction
    )

    assert (
        "[STACK_SETTLED]"
        in transaction
    )

    assert (
        "observer.clear_quantitative_ownership("
        in transaction
    )

    assert (
        "state.settlement_gate.clear_seat("
        in transaction
    )

    semantic_tokens = (
        "state.settlement_gate.observe(",
        "admit_quantitative_observation",
        "[QUANTITATIVE_DEFERRED]",
        "[STACK_SETTLED]",
    )

    for token in semantic_tokens:
        assert token not in run, (
            "semantic ownership leaked into "
            "run_hand: "
            f"{token}"
        )

    print(
        "V0.17 LIVE SAFETY BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
