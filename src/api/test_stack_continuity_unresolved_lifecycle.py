"""
RED contract for quantitative stack evidence outside the ordinary
continuity-selection window.

Purpose
-------
A physically evidenced stack candidate can produce repeated, coherent
numeric OCR evidence that is outside the ordinary continuity search
window.

That condition is NOT equivalent to OCR failure.

The continuity resolver is allowed to refuse promotion of the numeric
value. Downstream semantic stack validation remains authoritative.

But repeated coherent numeric evidence must not be destroyed merely by
being converted into the generic low-confidence OCR-failure lifecycle.

This test intentionally contains no replay-specific values, player
names, seats, pot arithmetic, or hand oracle.
"""

from src.vision.stack_candidate_resolver import resolve_stack_candidates


def test_repeated_numeric_candidate_outside_ordinary_window_is_not_ocr_absence():
    previous = 20.0

    # Repeated independent OCR observations agree on a real numeric
    # candidate, but the decrease exceeds the ordinary 3 BB continuity
    # search window.
    candidates = [16.5, 16.5, 16.5]

    resolution = resolve_stack_candidates(
        candidates,
        previous_stack_bb=previous,
        maximum_drop_bb=3.0,
    )

    assert resolution.resolved is False
    assert resolution.reason == "nearest_candidate_exceeds_drop_bound"

    # Contract:
    #
    # This is quantitative disagreement with the continuity prior,
    # NOT absence/failure of OCR.
    #
    # The coordinator must preserve this distinction so candidate
    # lifecycle policy can keep physically evidenced observations
    # unresolved without authorizing the transition.
    assert getattr(
        resolution,
        "numeric_evidence_present",
        False,
    ) is True


if __name__ == "__main__":
    test_repeated_numeric_candidate_outside_ordinary_window_is_not_ocr_absence()
    print(
        "PASS: out-of-window numeric evidence remains distinguishable "
        "from OCR absence"
    )
