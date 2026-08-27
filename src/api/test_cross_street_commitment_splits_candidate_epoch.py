from unittest.mock import patch

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"


def main():
    state = c.fresh_state()

    state["hand_token"] = "candidate-epoch-split-test"
    state["phase"] = "TURN"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 100.0,
            "last_change_ts": 100.0,
            "max_mean_diff": 5.0,
            "origin_street": "TURN",
            "trigger_sources": ["stack_motion"],
            "unchanged_stack_reads": 7,
            "ocr_attempts": 0,
            "validation_attempts": 0,
            "retry_not_before_ts": 101.0,
            "retry_frame_path": "/tmp/old_turn_frame.png",
            "retry_frame_ts": 101.0,
            "stack_worker_request_id": None,
            "hand_token": "candidate-epoch-split-test",
        }
    }

    state["pending_boundary_route"] = {
        "hand_token": state["hand_token"],
        "previous_street": "TURN",
        "next_street": "RIVER",
        "frames": [],
        "old_street_owing_seats": [SEAT],
        "required_event_cursor": None,
    }

    changes = ChangeSet()
    changes.bet_region_appeared = [SEAT]

    emitted = []

    with patch.object(
        c,
        "emit",
        side_effect=lambda event: emitted.append(dict(event)),
    ):
        c.process_stack_change_measurements_async(
            changes,
            None,
            state,
            stack_worker_results={},
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street="RIVER",
            old_street_owing_seats={SEAT},
            frame_path="/tmp/new_river_frame.png",
            frame_ts=128.0,
            replay_records=[],
        )

    print("pending:", state["pending_stack_reads"])
    print("events:", emitted)

    closures = [
        event
        for event in emitted
        if (
            event.get("type") == "stack_candidate_closed"
            and event.get("seat") == SEAT
            and event.get("street") == "TURN"
        )
    ]

    openings = [
        event
        for event in emitted
        if (
            event.get("type") == "stack_candidate_opened"
            and event.get("seat") == SEAT
            and event.get("street") == "RIVER"
        )
    ]

    assert len(closures) == 1, (
        "RED: stale TURN candidate was not explicitly closed "
        "when genuinely new RIVER commitment began"
    )

    assert len(openings) == 1, (
        "RED: genuinely new RIVER commitment did not open "
        "a new candidate epoch"
    )

    entry = state["pending_stack_reads"][SEAT]

    assert entry["origin_street"] == "RIVER", (
        "RED: replacement candidate does not belong to RIVER"
    )

    assert entry.get("trigger_sources") == [
        "bet_region_appeared"
    ], entry

    assert float(entry.get("first_change_ts")) == 128.0
    assert float(entry.get("last_change_ts")) == 128.0

    assert entry.get("retry_frame_path") is None
    assert entry.get("retry_frame_ts") is None

    print(
        "PASS: new cross-street commitment closes stale old "
        "candidate and starts a new street-local candidate epoch"
    )


if __name__ == "__main__":
    main()
