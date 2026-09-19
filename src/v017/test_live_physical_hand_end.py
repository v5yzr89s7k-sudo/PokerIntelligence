"""
V0.17 physical hand-end ownership contract.

Hero-card disappearance remains the bounded physical hand-end fallback,
but raw detector event order may not terminate the hand before all
evidence from the same physical frame receives its chronology
opportunity.

Required order:

    detect Hero-card disappearance
        -> retain frame card evidence
        -> process frame evidence
        -> reconcile frame evidence
        -> if Hero disappearance did not become semantic action:
               PHYSICAL_HAND_END
               return

The fallback is physical lifecycle ownership only. It must not restore
raw-event-order semantic authority.
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

    # Frame-level card retention must occur before reconciliation.
    retain = run.index(
        "retain_frame_card_disappearances("
    )

    reconcile = run.index(
        "reconcile_frame_evidence("
    )

    assert retain < reconcile

    # The runner explicitly remembers whether Hero disappeared during
    # this physical frame.
    assert (
        "hero_cards_disappeared_this_frame"
        in run
    )

    # Reconciliation records whether that disappearance acquired
    # legitimate semantic authority.
    assert (
        "hero_card_action_reconciled"
        in run
    )

    physical_end = run.index(
        "[PHYSICAL_HAND_END]"
    )

    # Physical termination may occur only after the complete-frame
    # chronology transaction.
    assert reconcile < physical_end

    # The fallback condition must distinguish unresolved physical
    # disappearance from an already-reconciled Hero action.
    fallback_start = run.rfind(
        "if (",
        reconcile,
        physical_end,
    )

    assert fallback_start >= 0

    fallback = run[
        fallback_start:
        physical_end + 500
    ]

    assert (
        "hero_cards_disappeared_this_frame"
        in fallback
    )

    assert (
        "not hero_card_action_reconciled"
        in fallback
    )

    assert "[PHYSICAL_HAND_END]" in fallback
    assert "return" in fallback

    # Never restore immediate card-disappearance semantic admission.
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

    print(
        "HERO DISAPPEARANCE RETAINED FIRST: PASS"
    )
    print(
        "COMPLETE FRAME RECONCILED FIRST: PASS"
    )
    print(
        "UNRESOLVED HERO DISAPPEARANCE -> HAND END: PASS"
    )
    print(
        "RAW EVENT ORDER TERMINATES HAND: NO"
    )
    print(
        "V0.17 PHYSICAL HAND OWNERSHIP: PASS"
    )


if __name__ == "__main__":
    main()
