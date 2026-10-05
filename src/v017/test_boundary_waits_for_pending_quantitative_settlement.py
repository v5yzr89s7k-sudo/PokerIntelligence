"""
Regression contract:

A physical next-street boundary must not use unknown-completion
authority to overtake a quantitative candidate first observed on
that same physical frame.

The quantitative candidate owns unresolved chronology until it is
confirmed or otherwise retired.  Only then may the retained physical
boundary reconcile.

This reproduces the live lifecycle:

    frame N:
        quantitative stack transition first observed
        FLOP boundary physically appears

    frame N+1:
        same quantitative value confirms

Required chronology:
        quantitative PREFLOP action
        then FLOP transition
"""

from pathlib import Path


RUNNER = Path("src/v017/run_live_observer.py")
OBSERVER = Path("src/v017/frame_hand_observer.py")


def main():
    runner = RUNNER.read_text()
    observer = OBSERVER.read_text()

    # Existing evidence-order contract must remain intact.
    assert "non_boundary_events = tuple(" in runner
    assert "boundary_events = tuple(" in runner
    assert "state.settlement_gate.observe(" in runner

    # Production currently grants a physical boundary authority to
    # complete unresolved actors.  That authority is the regression
    # target when a quantitative candidate is still pending.
    assert "observer.admit_street_boundary(" in runner
    assert "complete_pending=True" in runner

    # The architecture already has retained-boundary reconciliation.
    assert "reconcile_pending_evidence()" in runner
    assert "reconcile_pending_street_boundaries()" in runner

    quantitative_pos = runner.index(
        "reconcile_pending_evidence()"
    )
    boundary_pos = runner.index(
        "reconcile_pending_street_boundaries()"
    )

    assert quantitative_pos < boundary_pos, (
        "retained boundary reconciliation must remain after "
        "quantitative reconciliation"
    )

    # RED CONTRACT:
    #
    # Before a physical boundary may invoke complete_pending=True,
    # production must explicitly guard against unresolved quantitative
    # settlement ownership from the predecessor street.
    #
    # The implementation does not have this guard yet.
    required_guard = (
        "BOUNDARY_WAITING_FOR_QUANTITATIVE_SETTLEMENT"
    )

    assert required_guard in runner, (
        "RED: physical street boundary can overtake a pending "
        "two-frame quantitative settlement candidate"
    )

    print(
        "BOUNDARY / QUANTITATIVE SETTLEMENT ORDER: PASS"
    )


if __name__ == "__main__":
    main()
