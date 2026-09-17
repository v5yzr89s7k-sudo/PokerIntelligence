"""
Structural safety contract for the v0.17 live runner.

Raw quantitative OCR must never directly mutate HandEngine.

Live quantitative semantic admission is allowed only after:
    STACK_QUANTITATIVE_OBSERVATION
        -> StackSettlementGate.observe()
        -> non-None settlement
        -> admit_quantitative_observation()

The settlement gate is instantiated per physical hand, so pending
quantitative evidence cannot cross hand ownership boundaries.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
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
    source = RUNNER.read_text()
    tree = ast.parse(source)

    run = get_function(
        source,
        tree,
        "run_hand",
    )

    # --------------------------------------------------------
    # Per-hand ownership.
    # --------------------------------------------------------

    assert (
        "settlement_gate = "
        "StackSettlementGate()"
        in run
    )

    # --------------------------------------------------------
    # Raw quantitative evidence remains observable.
    # --------------------------------------------------------

    assert (
        '"STACK_QUANTITATIVE_OBSERVATION"'
        in run
    )

    assert (
        "[QUANTITATIVE_DEFERRED]"
        in run
    )

    # --------------------------------------------------------
    # Settlement must occur before semantic admission.
    # --------------------------------------------------------

    settle = run.index(
        "settlement_gate.observe("
    )

    admission = run.index(
        "admit_quantitative_observation"
    )

    assert settle < admission

    # Admission must live in the successful-settlement branch.
    settled_branch = run[
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

    # --------------------------------------------------------
    # No direct HandEngine stack mutation in the runner.
    # FrameHandObserver remains semantic owner.
    # --------------------------------------------------------

    forbidden = (
        ".observe_stack_commitment(",
        ".trusted_stacks[",
        "hand.observe_stack_commitment(",
    )

    for token in forbidden:
        assert token not in run, (
            "live runner bypasses semantic boundary: "
            f"{token}"
        )

    # --------------------------------------------------------
    # Existing physical hand-end safety remains present.
    # --------------------------------------------------------

    assert (
        "HERO_CARDS_DISAPPEARED_PHYSICAL"
        in run
    )

    assert (
        "[PHYSICAL_HAND_END]"
        in run
    )

    # --------------------------------------------------------
    # Settlement observability.
    # --------------------------------------------------------

    assert (
        "[STACK_SETTLED]"
        in run
    )

    assert (
        "observer.clear_quantitative_ownership("
        in source
    ), (
        "successful live quantitative admission must "
        "clear observer-owned physical work"
    )

    assert (
        "settlement_gate.clear_seat("
        in source
    ), (
        "successful live quantitative admission must "
        "clear settlement candidate ownership"
    )

    print(
        "V0.17 LIVE SAFETY BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
