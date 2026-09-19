"""
V0.17 live terminal stack-return wiring contract.

A post-terminal winner stack increase must be offered to the narrow
terminal-accounting authority lane before ordinary wager settlement.

If terminal accounting consumes the physical observation, the same
observation must never reach StackSettlementGate.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PATH = (
    ROOT
    / "src/v017/run_live_observer.py"
)


def get_function(
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

    run = get_function(
        source,
        tree,
        "run_hand",
    )

    quantitative = run.index(
        '== "STACK_QUANTITATIVE_OBSERVATION"'
    )

    terminal = run.index(
        "admit_terminal_stack_return(",
        quantitative,
    )

    settlement = run.index(
        "settlement_gate.observe(",
        quantitative,
    )

    assert quantitative < terminal < settlement

    terminal_branch = run[
        terminal:
        settlement
    ]

    assert "if terminal_rows:" in terminal_branch
    assert "[TERMINAL_STACK_RETURN]" in terminal_branch

    # Consumed terminal accounting must not fall through into wager
    # settlement.
    assert "continue" in terminal_branch

    # Physical work is cleared once terminal accounting owns it.
    assert (
        "observer.clear_quantitative_ownership("
        in terminal_branch
    )

    assert (
        "settlement_gate.clear_seat("
        in terminal_branch
    )

    # The semantic/accounting rules remain owned by FrameHandObserver /
    # HandEngine, not duplicated in the live runner.
    forbidden = (
        "unmatched_commitment_bb(",
        "observe_uncalled_return(",
        'completion_reason == "UNCONTESTED"',
    )

    for token in forbidden:
        assert token not in terminal_branch, token

    print(
        "TERMINAL ACCOUNTING BEFORE WAGER SETTLEMENT: PASS"
    )
    print(
        "CONSUMED OBSERVATION FALLS THROUGH: NO"
    )
    print(
        "LIVE RUNNER DUPLICATES ACCOUNTING RULES: NO"
    )
    print(
        "V0.17 LIVE TERMINAL STACK RETURN WIRING: PASS"
    )


if __name__ == "__main__":
    main()
