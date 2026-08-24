from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "FLOP"

    state["pending_stack_reads"] = {
        SEAT: {
            "hand_token": "hand-1",
            "first_change_ts": 70.0,
            "last_change_ts": 70.0,
            "max_mean_diff": 2.0,
            "origin_street": "FLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            # This is the new lifecycle state required by
            # test_stack_candidate_bounded_unchanged_retries.
            "unchanged_stack_reads": 4,
            "validation_attempts": 0,
            "last_stack_sample_ts": 80.0,
            "retry_not_before_ts": 80.45,
            "retry_frame_path": "/tmp/0082_full.png",
            "retry_frame_ts": 82.0,
        }
    }

    changes = ChangeSet()

    # Stronger/newer commitment evidence starts a new physical
    # development window. The old unchanged-read history may not
    # retire this newly rearmed candidate.
    changes.bet_region_appeared = [
        SEAT
    ]

    c.enrich_stack_change_measurements(
        changes,
        None,
        state,
        prior_occupied_bet_regions=set(),
        prior_commitment_seats=set(),
        event_street="FLOP",
        frame_path="/tmp/0091_full.png",
        frame_ts=91.0,
        queue_stack_ocr=True,
        replay_records=[],
    )

    entry = state[
        "pending_stack_reads"
    ][SEAT]

    print(
        "entry after fresh commitment:",
        entry,
    )

    assert (
        int(
            entry.get(
                "unchanged_stack_reads"
            )
            or 0
        )
        == 0
    ), (
        "REGRESSION REPRODUCED: fresh physical commitment "
        "evidence did not reset consecutive trusted-unchanged "
        "history; a new real transition could inherit an old "
        "false-positive retirement budget"
    )

    assert (
        float(
            entry.get(
                "last_change_ts"
            )
            or 0.0
        )
        == 91.0
    )

    assert (
        entry.get(
            "retry_not_before_ts"
        )
        is None
    )

    assert (
        entry.get(
            "retry_frame_path"
        )
        is None
    )

    assert (
        entry.get(
            "retry_frame_ts"
        )
        is None
    )

    print(
        "PASS fresh physical evidence rearms "
        "trusted-unchanged retry lifecycle"
    )


if __name__ == "__main__":
    main()
