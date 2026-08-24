"""
Coordinator lifecycle contract for coherent numeric stack evidence
outside the ordinary continuity-selection window.

This test does NOT assert that the transition is accepted.

It asserts only that:
  - physical stack evidence opened a real quantitative candidate;
  - OCR produced coherent numeric evidence;
  - continuity refused promotion because the decrease exceeded its
    ordinary search window;
  - that condition must not be treated identically to absent/bad OCR;
  - therefore it must not exhaust the generic OCR-attempt budget and
    destroy the physical candidate.

No player identity, replay fixture, pot value, or real-hand numeric
constant is encoded here.
"""

from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_mid_right"


def main():
    state = c.fresh_state()

    state["phase"] = "FLOP"
    state["hand_token"] = "synthetic-hand"

    # Canonical baseline is intentionally synthetic.
    canonical_values = {
        SEAT: 20.0,
    }

    changes = ChangeSet(
        stack_changed_seats=[SEAT],
        stack_change_details={
            SEAT: {
                "mean_diff": 12.0,
            }
        },
    )

    # Repeated coherent numeric evidence lies outside the ordinary
    # 3 BB continuity search window.
    #
    # The exact values are arbitrary synthetic test values.
    # Two DISTINCT ordinary candidates are required to exercise
    # production's continuity resolver. Both are non-increasing,
    # and even the nearest candidate lies outside the ordinary
    # continuity window.
    #
    # Independent evidence deliberately supplies no authoritative
    # confirmation so the separate independent-confirmation path
    # cannot bypass continuity resolution.
    reading = {
        "raw": [
            {
                "variant": "a",
                "raw": "16.5 BB",
                "stack_bb": 16.5,
            },
            {
                "variant": "b",
                "raw": "16.4 BB",
                "stack_bb": 16.4,
            },
            {
                "variant": "c",
                "raw": "16.5 BB",
                "stack_bb": 16.5,
            },
        ],
        "stack_bb": 16.5,
        "stack_text": "16.5 BB",
        "confidence": 0.98,
        "votes": 3,
        "mode": "synthetic_consensus",
    }

    independent = {
        "stack_bb": None,
        "stack_text": "",
        "confidence": 0.0,
        "votes": 0,
        "mode": "synthetic_unresolved",
        "raw": [],
    }

    emitted = []

    img = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    with (
        patch.object(
            c,
            "_canonical_stack_values",
            return_value=canonical_values,
        ),
        patch.object(
            c,
            "read_stack",
            return_value=dict(reading),
        ),
        patch.object(
            c,
            "read_stack_independent_consensus",
            return_value=dict(independent),
        ),
        patch.object(
            c,
            "emit",
            side_effect=lambda event: emitted.append(
                dict(event)
            ),
        ),
    ):
        # Repeated settlement attempts model the current lifecycle
        # behavior. A continuity-prior rejection must not be converted
        # into generic OCR exhaustion.
        for attempt in range(6):
            now = 100.0 + attempt

            pending = state.setdefault(
                "pending_stack_reads",
                {},
            )

            if SEAT not in pending:
                if attempt == 0:
                    pass
                else:
                    break

            current_changes = (
                changes
                if attempt == 0
                else ChangeSet()
            )

            c.enrich_stack_change_measurements(
                current_changes,
                img=img,
                state=state,
                frame_ts=now,
                queue_stack_ocr=False,
            )

    pending = state.get(
        "pending_stack_reads"
    ) or {}

    entry = pending.get(SEAT)

    print(
        "candidate survives:",
        entry is not None,
    )

    print(
        "candidate:",
        entry,
    )

    print(
        "emitted stack updates:",
        [
            item
            for item in emitted
            if item.get("type") == "stack_update"
        ],
    )

    # Safety invariant: out-of-window numeric evidence must NEVER
    # silently become an accepted stack transition here.
    assert not any(
        item.get("type") == "stack_update"
        for item in emitted
    ), (
        "out-of-window numeric evidence was incorrectly promoted"
    )

    # RED contract:
    #
    # Coherent numeric evidence rejected by continuity is unresolved
    # quantitative evidence, not generic OCR absence. It must not
    # disappear solely because the OCR-attempt budget was consumed.
    assert entry is not None, (
        "REPRODUCED: coherent out-of-window numeric evidence "
        "was exhausted as generic OCR failure and the physical "
        "candidate was destroyed"
    )

    assert int(
        entry.get("ocr_attempts")
        or 0
    ) == 0, (
        "REPRODUCED: continuity-prior rejection consumed the "
        "generic OCR-failure budget"
    )

    print(
        "PASS: coherent out-of-window numeric evidence remains "
        "unresolved without being promoted or exhausted as OCR failure"
    )


if __name__ == "__main__":
    main()
