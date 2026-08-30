"""
Regression contract:

A raw stack-motion-only candidate is weak quantitative evidence.

Once one trusted settled OCR read proves that the canonical stack is
unchanged, the candidate must close immediately rather than consuming
the five-read retry budget.

Independent commitment evidence remains protected:
a candidate carrying bet_region_appeared may legitimately survive an
unchanged first read because the numeric stack display can lag chips.
"""

from types import SimpleNamespace
from unittest.mock import patch

import src.api.api_event_coordinator as c


SEAT = "seat_upper_left"
STREET = "PREFLOP"
STACK = 59.08


def changes_for(seat):
    return SimpleNamespace(
        stack_changed_seats=[],
        stack_change_details={},
        ui_activity_seats=[],
        bet_region_appeared=[],
        bet_region_cleared=[],
        bet_region_occupancy={},
        bet_region_transitions={},
    )


def trusted_unchanged_result(request_id):
    return {
        "request_id": request_id,
        "hand_token": "motion-only-close-test",
        "seat": SEAT,
        "street": STREET,
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": STACK,
            "stack_text": f"{STACK:g} BB",
            "confidence": 0.98,
            "votes": 2,
            "mode": "agreement",
            "raw": [
                {"stack_bb": STACK},
                {"stack_bb": STACK},
            ],
        },
        "independent": {},
    }


def make_state(sources):
    request_id = "motion-only-request"

    return {
        "hand_token": "motion-only-close-test",
        "phase": STREET,
        "pending_stack_reads": {
            SEAT: {
                "first_change_ts": 100.0,
                "last_change_ts": 100.0,
                "last_stack_sample_ts": 101.0,
                "max_mean_diff": 12.0,
                "origin_street": STREET,
                "trigger_sources": list(sources),
                "stack_worker_request_id": request_id,
            },
        },
        "pending_stack_worker_requests": {},
    }, request_id


def run_case(sources):
    state, request_id = make_state(sources)

    worker_item = {
        "request_id": request_id,
        "request": {
            "request_id": request_id,
            "hand_token": state["hand_token"],
            "seat": SEAT,
            "street": STREET,
            "purpose": "settled",
        },
        "result": trusted_unchanged_result(request_id),
    }

    changes = changes_for(SEAT)

    with patch.object(
        c,
        "_canonical_stack_values",
        return_value={SEAT: STACK},
    ):
        c.enrich_stack_change_measurements(
            changes,
            img=None,
            state=state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street=STREET,
            old_street_owing_seats=set(),
            frame_path="synthetic.png",
            frame_ts=102.0,
            stack_worker_results={
                SEAT: worker_item,
            },
            queue_stack_ocr=True,
            replay_records=None,
        )

    return state


def main():
    print("===== MOTION-ONLY TRUSTED UNCHANGED =====")

    motion_state = run_case(
        ["stack_motion"]
    )

    motion_pending = (
        motion_state
        .get("pending_stack_reads", {})
    )

    print(
        "candidate remains:",
        SEAT in motion_pending,
    )

    assert SEAT not in motion_pending, (
        "RED: motion-only candidate survives a trusted "
        "unchanged stack read and therefore schedules redundant OCR"
    )

    print()
    print("===== INDEPENDENT COMMITMENT EVIDENCE =====")

    commitment_state = run_case(
        [
            "stack_motion",
            "bet_region_appeared",
        ]
    )

    commitment_pending = (
        commitment_state
        .get("pending_stack_reads", {})
    )

    print(
        "candidate remains:",
        SEAT in commitment_pending,
    )

    assert SEAT in commitment_pending, (
        "REGRESSION: independently evidenced commitment "
        "lost its protected delayed-stack retry window"
    )

    print()
    print(
        "PASS motion-only OCR retirement: trusted unchanged "
        "stack closes weak motion candidate after one read; "
        "bet-region commitment retains retry protection"
    )


if __name__ == "__main__":
    main()
