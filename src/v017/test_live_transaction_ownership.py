"""
V0.17 single live/simulation frame-transaction ownership contract.

run_hand owns acquisition/timing only.
process_frame_transaction owns semantic processing.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/run_live_observer.py"


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
    source = PATH.read_text()
    tree = ast.parse(source)

    transaction = get_function(
        source,
        tree,
        "process_frame_transaction",
    )

    live = get_function(
        source,
        tree,
        "run_hand",
    )

    semantic_tokens = (
        "observer.process_frame(",
        "retain_frame_card_disappearances(",
        "admit_terminal_stack_return(",
        "settlement_gate.observe(",
        "reconcile_frame_evidence(",
        "observe_no_commitment(",
        "[HERO_DISAPPEARANCE_RETAINED]",
        "[HAND_COMPLETE]",
    )

    for token in semantic_tokens:
        assert token in transaction, token
        assert token not in live, token

    assert "capture_image(window)" in live
    assert "process_frame_transaction(" in live
    assert "FRAME_INTERVAL_SECONDS" in live

    assert "capture_image(window)" not in transaction
    assert "time.sleep(" not in transaction

    # Every semantic outcome carries the physical events already
    # observed by the single production transaction. Diagnostics must
    # never require a second observer.process_frame() call.
    for outcome in (
        "HAND_COMPLETE",
        "CONTINUE",
    ):
        assert (
            f'"{outcome}",'
            in transaction
        )

    assert (
        '"PHYSICAL_HAND_END"'
        not in transaction
    )

    assert (
        transaction.count(
            "return FrameTransactionResult("
        )
        == 2
    )

    assert (
        transaction.count(
            "result.events,"
        )
        >= 2
    )

    assert "transaction.outcome" in live

    print(
        "SEMANTIC OWNER = process_frame_transaction: PASS"
    )
    print(
        "LIVE OWNER = acquisition/timing only: PASS"
    )
    print(
        "DUPLICATE LIVE SEMANTICS: NO"
    )
    print(
        "V0.17 LIVE TRANSACTION OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
