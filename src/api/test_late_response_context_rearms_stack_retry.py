from pathlib import Path

import src.api.api_event_coordinator as c


SEAT = "seat_lower_right"
STREET = "FLOP"

T92 = 1787780733.244864
T94 = 1787780734.886000
T96 = 1787780735.563000


def records():
    return [
        {
            "ts": T92,
            "frame_path": "/tmp/0092_full.png",
        },
        {
            "ts": T94,
            "frame_path": "/tmp/0094_full.png",
        },
        {
            "ts": T96,
            "frame_path": "/tmp/0096_full.png",
        },
    ]


def candidate():
    return {
        "first_change_ts": T92,
        "last_change_ts": T92,
        "origin_street": STREET,
        "trigger_sources": ["stack_motion"],
        "last_stack_sample_ts": T94,
        "unchanged_stack_reads": 2,
        "retry_not_before_ts": T96,
        "retry_frame_path": "/tmp/0096_full.png",
        "retry_frame_ts": T96,
        "hand_token": "hand-1",
    }


def main():
    state = c.fresh_state()
    state["hand_token"] = "hand-1"
    state["phase"] = STREET
    state["pending_stack_reads"] = {
        SEAT: candidate(),
    }

    entry = state["pending_stack_reads"][SEAT]

    # Model the problematic ordering:
    #
    # 1. physical stack candidate already exists;
    # 2. unchanged quantitative result has already been reconciled;
    # 3. semantic aggression context becomes authoritative afterward.
    #
    # The late semantic enrichment must not destroy or strand the
    # deterministic quantitative retry obligation.

    changes = c.ChangeSet()

    old_queue = c.queue_stack_worker_request

    queued = []

    def fake_queue(
        state,
        *,
        seat,
        street,
        frame_path,
        purpose,
    ):
        request_id = "request-0096"

        queued.append(
            (
                seat,
                street,
                Path(frame_path).name,
                purpose,
            )
        )

        state.setdefault(
            "pending_stack_worker_requests",
            {},
        )[request_id] = {
            "seat": seat,
            "street": street,
            "frame": frame_path,
            "purpose": purpose,
            "hand_token": state.get("hand_token"),
        }

        return request_id

    c.queue_stack_worker_request = fake_queue

    try:
        # Late semantic context arrives after the unchanged read.
        #
        # Exercise the production enrichment path without introducing
        # a new raw stack-motion or bet-region transition.
        c.enrich_stack_change_measurements(
            changes,
            img=None,
            state=state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats={SEAT},
            event_street=STREET,
            frame_path="/tmp/0096_full.png",
            frame_ts=T96,
            stack_worker_results={},
            queue_stack_ocr=True,
            replay_records=records(),
        )

    finally:
        c.queue_stack_worker_request = old_queue

    entry = (
        state.get("pending_stack_reads")
        or {}
    ).get(SEAT)

    print("queued:", queued)
    print("candidate:", entry)
    print(
        "transport:",
        state.get(
            "pending_stack_worker_requests"
        ),
    )

    assert entry is not None, (
        "RED: late response context destroyed "
        "the existing physical candidate"
    )

    assert (
        "response_to_aggression"
        in set(entry.get("trigger_sources") or [])
    ), (
        "RED: late response context was not "
        "persisted on the candidate"
    )

    assert queued == [
        (
            SEAT,
            STREET,
            "0096_full.png",
            "settled",
        )
    ], (
        "RED: late response context did not preserve/re-arm "
        "the deterministic 0096 quantitative retry obligation"
    )

    assert (
        entry.get("stack_worker_request_id")
        == "request-0096"
    ), (
        "RED: candidate does not own the deterministic "
        "0096 retry"
    )

    assert (
        "request-0096"
        in (
            state.get(
                "pending_stack_worker_requests"
            )
            or {}
        )
    ), (
        "RED: transport does not own the deterministic "
        "0096 retry"
    )

    print(
        "PASS late response context preserves deterministic "
        "stack retry ownership"
    )


if __name__ == "__main__":
    main()
