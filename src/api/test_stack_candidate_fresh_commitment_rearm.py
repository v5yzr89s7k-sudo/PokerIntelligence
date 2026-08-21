from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"
    state["phase"] = "FLOP"

    # Existing candidate originated from earlier weak stack-motion evidence.
    #
    # It has already produced unchanged settled reads and therefore carries
    # retry scheduling derived from that earlier physical episode.
    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 73.0,
            "last_change_ts": 73.0,
            "max_mean_diff": 1.0,
            "origin_street": "FLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "ocr_attempts": 0,
            "validation_attempts": 0,
            "last_stack_sample_ts": 87.0,
            "retry_not_before_ts": 87.45,
            "retry_frame_path": "/tmp/0089_full.png",
            "retry_frame_ts": 89.0,
            "stack_worker_request_id": None,
            "hand_token": "hand-1",
        }
    }

    changes = ChangeSet()

    # This models the real July 22 frame-91 event:
    # new independent commitment evidence arrives substantially later.
    changes.bet_region_appeared = [
        SEAT
    ]

    # We only need to exercise candidate mutation. Keep semantic time inside
    # the new settlement window so this call cannot queue/read another stack.
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

    print("entry:", entry)

    assert (
        "bet_region_appeared"
        in entry.get("trigger_sources", [])
    ), (
        "REPRODUCED: fresh same-street commitment "
        "evidence did not attach to existing candidate"
    )

    assert (
        float(entry.get("last_change_ts") or 0)
        == 91.0
    ), (
        "REPRODUCED: fresh commitment evidence did "
        "not refresh candidate settlement time"
    )

    # REQUIRED INVARIANT:
    #
    # Retry scheduling chosen from the earlier stack-motion episode may not
    # survive stronger, newer physical commitment evidence. The candidate must
    # settle again relative to frame 91 and sample a post-commitment frame.
    assert (
        entry.get("retry_not_before_ts")
        is None
    ), (
        "REPRODUCED: stale retry deadline survived "
        "fresh same-street commitment evidence"
    )

    assert (
        entry.get("retry_frame_path")
        is None
    ), (
        "REPRODUCED: stale retry frame survived "
        "fresh same-street commitment evidence"
    )

    assert (
        entry.get("retry_frame_ts")
        is None
    ), (
        "REPRODUCED: stale retry timestamp survived "
        "fresh same-street commitment evidence"
    )

    print(
        "PASS fresh commitment rearm: stronger newer "
        "same-street evidence refreshes candidate timing "
        "and invalidates stale retry scheduling"
    )


if __name__ == "__main__":
    main()
