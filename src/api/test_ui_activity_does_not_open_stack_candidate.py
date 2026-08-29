"""
Regression contract for the fast physical UI lane.

Pure deterministic bottom-strip/nameplate UI animation may still appear in
legacy stack_changed_seats, but it must not create a quantitative stack
candidate by itself.

Independent commitment evidence must continue to create a candidate.
"""

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "hero"


def make_state():
    return {
        "phase": "TURN",
        "hand_token": "ui-activity-stack-candidate-test",
        "pending_stack_reads": {},
        "pending_stack_worker_requests": {},
    }


def pure_ui_changes():
    changes = ChangeSet()

    changes.stack_changed_seats = [
        SEAT,
    ]

    changes.stack_change_details = {
        SEAT: {
            "mean_diff": 5.83,
            "threshold": 4.0,
            "changed": True,
        },
    }

    changes.ui_activity_seats = [
        SEAT,
    ]

    return changes


def committed_changes():
    changes = pure_ui_changes()

    changes.bet_region_appeared = [
        SEAT,
    ]

    return changes


def run(changes):
    state = make_state()

    c.enrich_stack_change_measurements(
        changes,
        None,
        state,
        prechange_image=None,
        prior_occupied_bet_regions=set(),
        prior_commitment_seats=set(),
        response_to_aggression_seats=set(),
        event_street="TURN",
        old_street_owing_seats=set(),
        recent_stack_observations={},
        frame_path="",
        frame_ts=100.0,
        stack_worker_results={},
        queue_stack_ocr=False,
        replay_records=None,
        replay_eof=False,
    )

    return state


def main():

    print(
        "===== PURE UI ACTIVITY ====="
    )

    state = run(
        pure_ui_changes()
    )

    pending = (
        state.get(
            "pending_stack_reads"
        )
        or {}
    )

    print(
        "pending:",
        pending,
    )

    assert SEAT not in pending, (
        "RED: pure ui_activity still opened "
        "a quantitative stack candidate"
    )

    print()
    print(
        "===== UI + COMMITMENT EVIDENCE ====="
    )

    state = run(
        committed_changes()
    )

    pending = (
        state.get(
            "pending_stack_reads"
        )
        or {}
    )

    print(
        "pending:",
        pending,
    )

    assert SEAT in pending, (
        "REGRESSION: independent bet-region evidence "
        "failed to retain quantitative stack ownership"
    )

    sources = set(
        pending[SEAT].get(
            "trigger_sources"
        )
        or []
    )

    print(
        "sources:",
        sorted(sources),
    )

    assert (
        "bet_region_appeared"
        in sources
    ), (
        "REGRESSION: commitment source missing"
    )

    print()
    print(
        "PASS UI/quantitative lane split: "
        "pure UI animation cannot open OCR ownership; "
        "independent commitment evidence still can"
    )


if __name__ == "__main__":
    main()
