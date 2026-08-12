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
            "src.api.api_event_coordinator._canonical_stack_values",
            return_value={"hero": previous_stack},
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


def test_zero_stack_is_retried_without_all_in_confirmation():
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

    pending = state["pending_stack_reads"]["hero"]
    assert pending["validation_attempts"] == 1
    assert pending["origin_street"] == "PREFLOP"


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

    # The coordinator emits the authoritative transition but does not
    # maintain a second persistent stack baseline. CanonicalHand is updated
    # later by the API event state machine.
    assert state["live_stack_bb_by_seat"]["hero"] == 39.38
    assert "hero" not in state["pending_stack_reads"]


def test_bet_region_appearance_schedules_stack_read_without_raw_motion():
    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
    }

    changes = ChangeSet()
    changes.bet_region_appeared = ["seat_mid_left"]

    image = np.zeros((696, 934, 3), dtype=np.uint8)

    now = time.time()

    # First pass: bet-region evidence creates a pending quantitative read.
    with (
        patch(
            "src.api.api_event_coordinator._canonical_stack_values",
            return_value={"seat_mid_left": 65.6},
        ),
        patch(
            "src.api.api_event_coordinator.read_stack",
            return_value={
                "stack_bb": 56.6,
                "stack_text": "56.6 BB",
                "confidence": 0.98,
                "votes": 2,
                "mode": "agreement",
                "raw": [],
            },
        ),
    ):
        enrich_stack_change_measurements(
            changes,
            image,
            state,
        )

        assert "seat_mid_left" in state["pending_stack_reads"]
        assert changes.stack_changed_seats == []

        # Simulate the normal 450ms settlement delay without sleeping.
        state["pending_stack_reads"]["seat_mid_left"]["last_change_ts"] = (
            now - 1.0
        )

        changes.bet_region_appeared = []

        enrich_stack_change_measurements(
            changes,
            image,
            state,
        )

    assert changes.stack_changed_seats == ["seat_mid_left"]

    measurement = changes.stack_change_details["seat_mid_left"]

    assert measurement["previous_stack_bb"] == 65.6
    assert measurement["current_stack_bb"] == 56.6
    assert measurement["delta_bb"] == 9.0
    assert "seat_mid_left" not in state["pending_stack_reads"]


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


def test_missing_canonical_baseline_times_out():
    state = make_state()
    state["pending_stack_reads"]["seat_lower_right"] = {
        "first_change_ts": time.time() - 5.0,
        "last_change_ts": time.time() - 4.0,
        "baseline_wait_started_ts": time.time() - 3.0,
        "baseline_wait_attempts": 10,
        "max_mean_diff": 4.0,
        "origin_street": "PREFLOP",
    }
    state["pending_stack_reads"].pop("hero", None)

    changes = make_changes()
    image = np.zeros((696, 934, 3), dtype=np.uint8)

    with patch(
        "src.api.api_event_coordinator._canonical_stack_values",
        return_value={},
    ):
        enrich_stack_change_measurements(
            changes,
            image,
            state,
        )

    assert changes.stack_changed_seats == []
    assert changes.stack_change_details == {}
    assert "seat_lower_right" not in state["pending_stack_reads"]

def main():
    test_zero_stack_is_retried_without_all_in_confirmation()
    test_single_vote_is_retried_without_mutating_baseline()
    test_trusted_decrease_is_accepted()
    test_bet_region_appearance_schedules_stack_read_without_raw_motion()
    test_positive_jump_does_not_mutate_baseline()
    test_missing_canonical_baseline_times_out()

    print("stack settlement safety tests passed")



if __name__ == "__main__":
    main()
