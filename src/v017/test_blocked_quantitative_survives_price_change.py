"""
Regression contract:

A settled quantitative observation that was retained only because
chronological predecessors were unresolved must not be destroyed merely
because reconciliation of one of those predecessors changes the current
betting price.

The retained observation belongs to the betting state under which its
physical stack transition occurred.
"""

from pathlib import Path


SOURCE = Path("src/v017/frame_hand_observer.py")


def main():
    s = SOURCE.read_text()

    assert "retained_current_price_bb" in s, (
        "retained price provenance is missing"
    )
    assert "blocked_predecessors" in s, (
        "blocked-predecessor retention path is missing"
    )
    assert "_retain_blocked_quantitative_evidence" in s, (
        "blocked quantitative retention helper is missing"
    )

    stale_marker = '"[STALE_QUANTITATIVE_RETIRED]"'
    assert stale_marker in s, (
        "expected stale quantitative retirement path not found"
    )

    start = s.index(
        "def reconcile_pending_quantitative_evidence"
    )
    end = s.index(
        "\n    def ",
        start + 10,
    )
    body = s[start:end]

    assert "retained_price" in body
    assert "current_price" in body
    assert "reason=betting_price_changed" in body

    # This is the defect contract. The current implementation should
    # FAIL this assertion until the production fix is applied.
    #
    # Chronology-blocked evidence must not be retired solely because
    # current_price later changed.
    retirement = body.index(
        "reason=betting_price_changed"
    )

    preceding = body[max(0, retirement - 1200):retirement]

    assert "blocked_predecessors" in preceding, (
        "EXPECTED FAIL: retained chronology-blocked quantitative "
        "evidence is currently retired solely on a later betting-price "
        "change. Production logic must distinguish temporal provenance "
        "from the later authoritative price."
    )

    print(
        "BLOCKED QUANTITATIVE PRICE-CHANGE CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
