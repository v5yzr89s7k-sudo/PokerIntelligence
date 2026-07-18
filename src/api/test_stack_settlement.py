import time
from unittest.mock import patch

import numpy as np

from src.api.api_event_coordinator import (
    enrich_stack_change_measurements,
)
from src.events.local_event_detector import ChangeSet


def make_state(previous_stack=39.38):
    return {
        "live_stack_bb_by_seat": {
            "hero": previous_stack,
        },
        "pending_stack_reads": {
            "hero": {
                "first_change_ts": time.time() - 2.0,
                "last_change_ts": time.time() - 1.0,
                "max_mean_diff": 5.25,
                "origin_street": "PREFLOP",
            },
        },
    }


def make_changes():
    # The movement has already been captured in pending_stack_reads.
    # No new raw movement is required during the settlement frame.
    return ChangeSet()


def run_settlement(reading, previous_stack=39.38):
    state = make_state(previous_stack)
    changes = make_changes()
    image = np.zeros((696, 934, 3), dtype=np.uint8)

    with (
        patch(
            "src.api.api_event_coordinator._snapshot_stack_values",
            return_value={},
        ),
        patch(
            "src.api.api_event_coordinator.read_stack",
            return_value=reading,
        ),
    ):
        enrich_stack_change_measurements(
            changes,
            image,
            state,
        )

    return changes, state


def test_zero_stack_is_rejected():
    changes, state = run_settlement({
        "stack_bb": 0.0,
        "stack_text": "0 BB",
        "confidence": 0.95,
        "votes": 2,
        "mode": "tiebreak",
    })

    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}
    assert state["live_stack_bb_by_seat"]["hero"] == 39.38
    assert "hero" not in state["pending_stack_reads"]


def test_single_vote_is_retried_without_mutating_baseline():
    changes, state = run_settlement({
        "stack_bb": 27.38,
        "stack_text": "27.38 BB",
        "confidence": 0.75,
        "votes": 1,
        "mode": "plain_only",
    })

    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}
    assert state["live_stack_bb_by_seat"]["hero"] == 39.38

    pending = state["pending_stack_reads"]["hero"]
    assert pending["ocr_attempts"] == 1
    assert pending["origin_street"] == "PREFLOP"


def test_trusted_decrease_is_accepted():
    changes, state = run_settlement({
        "stack_bb": 27.38,
        "stack_text": "27.38 BB",
        "confidence": 0.98,
        "votes": 2,
        "mode": "agreement",
    })

    assert changes.stack_changed_seats == ["hero"]

    measurement = changes.stack_change_details["hero"]

    assert measurement["previous_stack_bb"] == 39.38
    assert measurement["current_stack_bb"] == 27.38
    assert measurement["delta_bb"] == 12.0
    assert measurement["stack_read_confidence"] == 0.98
    assert measurement["stack_read_mode"] == "agreement"

    assert state["live_stack_bb_by_seat"]["hero"] == 27.38
    assert "hero" not in state["pending_stack_reads"]


def test_positive_jump_does_not_mutate_baseline():
    changes, state = run_settlement({
        "stack_bb": 91.75,
        "stack_text": "91.75 BB",
        "confidence": 0.98,
        "votes": 2,
        "mode": "agreement",
    })

    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}
    assert state["live_stack_bb_by_seat"]["hero"] == 39.38
    assert "hero" not in state["pending_stack_reads"]


def main():
    test_zero_stack_is_rejected()
    test_single_vote_is_retried_without_mutating_baseline()
    test_trusted_decrease_is_accepted()
    test_positive_jump_does_not_mutate_baseline()

    print("stack settlement safety tests passed")


if __name__ == "__main__":
    main()
