"""
V0.17 Hero-card disappearance lifecycle contract.

Hero-card disappearance is objective action evidence, not poker-hand
termination.

Required ownership:

    detect Hero-card disappearance
        -> retain frame card evidence
        -> process complete frame evidence
        -> reconcile if Hero reaches authoritative actor frontier
        -> otherwise retain evidence
        -> CONTINUE observing the poker hand

Actual poker-hand termination remains canonical result ownership:
UNCONTESTED HandEngine completion or objective terminal WINNER evidence.
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
        "process_frame_transaction",
    )

    # Physical evidence remains observable.
    assert (
        "HERO_CARDS_DISAPPEARED_PHYSICAL"
        in run
    )

    # Complete-frame chronology remains mandatory.
    retain = run.index(
        "retain_frame_card_disappearances("
    )

    reconcile = run.index(
        "reconcile_frame_evidence("
    )

    assert retain < reconcile

    # Transaction remembers physical Hero disappearance.
    assert (
        "hero_cards_disappeared_this_frame"
        in run
    )

    # Reconciliation still records whether Hero disappearance
    # acquired legitimate semantic authority this frame.
    assert (
        "hero_card_action_reconciled"
        in run
    )

    # An unresolved Hero disappearance is retained, not terminal.
    assert (
        "[HERO_DISAPPEARANCE_RETAINED]"
        in run
    )

    assert (
        "hand_continues=True"
        in run
    )

    # Hero disappearance must never itself return a physical
    # poker-hand termination outcome.
    assert (
        '"PHYSICAL_HAND_END"'
        not in run
    )

    assert (
        "[PHYSICAL_HAND_END]"
        not in run
    )

    # Never restore immediate raw-event semantic authority.
    card_branch_start = run.index(
        'if typ in {'
    )

    card_branch_end = run.index(
        '== "HERO_ACTION_BUTTONS_APPEARED"',
        card_branch_start,
    )

    card_branch = run[
        card_branch_start:
        card_branch_end
    ]

    assert (
        "admit_card_disappearance("
        not in card_branch
    )

    # Canonical terminal result ownership remains present.
    assert (
        "detect_winner("
        in run
    )

    assert (
        "observer.admit_terminal_boundary("
        in run
    )

    assert (
        "if observer.hand.hand_complete:"
        in run
    )

    assert (
        '"HAND_COMPLETE"'
        in run
    )

    print(
        "HERO DISAPPEARANCE RETAINED FIRST: PASS"
    )

    print(
        "UNRESOLVED HERO DISAPPEARANCE -> CONTINUE: PASS"
    )

    print(
        "HERO FOLD != HAND END: PASS"
    )

    print(
        "CANONICAL RESULT OWNS HAND END: PASS"
    )

    print(
        "V0.17 HERO FOLD CONTINUATION OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
