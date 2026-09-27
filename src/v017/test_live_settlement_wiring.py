from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src/v017/run_live_observer.py"


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
    source = PATH.read_text()
    tree = ast.parse(source)

    run = function_source(
        source,
        tree,
        "run_hand",
    )

    transaction = function_source(
        source,
        tree,
        "process_frame_transaction",
    )

    assert "StackSettlementGate" in source

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
        "state.settlement_gate.observe("
        in transaction
    )

    assert (
        "observer.hand.street"
        in transaction
    )

    assert (
        "admit_quantitative_observation"
        in transaction
    )

    assert (
        "[QUANTITATIVE_DEFERRED]"
        in transaction
    )

    assert (
        "[STACK_SETTLED]"
        in transaction
    )

    settle_index = transaction.index(
        "state.settlement_gate.observe("
    )

    admission_index = transaction.index(
        "admit_quantitative_observation"
    )

    assert settle_index < admission_index

    assert (
        "state.settlement_gate.observe("
        not in run
    )

    assert (
        "admit_quantitative_observation"
        not in run
    )

    print(
        "V0.17 LIVE SETTLEMENT WIRING: PASS"
    )


if __name__ == "__main__":
    main()
