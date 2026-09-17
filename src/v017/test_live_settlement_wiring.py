from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

PATH = (
    ROOT
    / "src/v017/run_live_observer.py"
)


def function_source(
    source,
    tree,
    name,
):
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

    assert (
        "StackSettlementGate"
        in source
    )

    # One fresh gate belongs to each run_hand invocation.
    assert (
        "settlement_gate = "
        "StackSettlementGate()"
        in run
    )

    assert (
        "settlement_gate.observe("
        in run
    )

    assert (
        "observer.hand.street"
        in run
    )

    assert (
        "admit_quantitative_observation"
        in run
    )

    assert (
        "[QUANTITATIVE_DEFERRED]"
        in run
    )

    assert (
        "[STACK_SETTLED]"
        in run
    )

    # Semantic admission must be downstream of settlement.
    settle_index = run.index(
        "settlement_gate.observe("
    )

    admission_index = run.index(
        "admit_quantitative_observation"
    )

    assert (
        settle_index
        < admission_index
    )

    print(
        "V0.17 LIVE SETTLEMENT WIRING: PASS"
    )


if __name__ == "__main__":
    main()
