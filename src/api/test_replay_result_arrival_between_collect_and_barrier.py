import src.api.api_event_coordinator as c


REQUEST_ID = "request-0094"
SEAT = "seat_lower_right"
STREET = "FLOP"

CURRENT_TS = 94.0
NEXT_TS = 96.0


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-1"

    state["pending_stack_reads"] = {
        SEAT: {
            "first_change_ts": 90.0,
            "last_change_ts": 90.0,
            "origin_street": STREET,
            "trigger_sources": [
                "stack_motion",
                "response_to_aggression",
            ],
            "stack_worker_request_id": REQUEST_ID,
            "last_stack_sample_ts": 94.0,
            "unchanged_stack_reads": 1,
            "hand_token": "hand-1",
        }
    }

    state["pending_stack_worker_requests"] = {
        REQUEST_ID: {
            "seat": SEAT,
            "street": STREET,
            "frame": "/tmp/0094_full.png",
            "purpose": "settled",
            "hand_token": "hand-1",
        }
    }

    replay_records = [
        {
            "ts": CURRENT_TS,
            "frame_path": "/tmp/0094_full.png",
        },
        {
            "ts": NEXT_TS,
            "frame_path": "/tmp/0096_full.png",
        },
    ]

    completed_result = {
        "request_id": REQUEST_ID,
        "hand_token": "hand-1",
        "seat": SEAT,
        "street": STREET,
        "purpose": "settled",
        "ok": True,
        "reading": {
            "stack_bb": 56.55,
            "confidence": 0.98,
            "votes": 2,
            "mode": "tiebreak",
        },
        "independent": {
            "stack_bb": 56.55,
            "confidence": 0.98,
            "votes": 5,
        },
    }

    old_find = c.find_stack_worker_result
    old_release = c._replay_stack_request_release_ts

    calls = []

    def fake_find(request_id):
        assert request_id == REQUEST_ID

        calls.append(request_id)

        # Exact production race:
        #
        # First lookup occurs inside
        # collect_ready_stack_worker_results(): worker result has
        # not been published yet.
        #
        # Second lookup occurs moments later inside
        # replay_stack_semantic_barrier_allows_advance():
        # result has now appeared.
        if len(calls) == 1:
            return None

        return completed_result

    def fake_release(
        state,
        request_id,
        request,
        replay_records,
    ):
        assert request_id == REQUEST_ID

        # This request is semantically due exactly at the next
        # recorded frame.
        return NEXT_TS

    c.find_stack_worker_result = fake_find
    c._replay_stack_request_release_ts = fake_release

    try:
        result = c.reconcile_replay_stack_before_capture(
            state,
            current_frame_ts=CURRENT_TS,
            next_frame_ts=NEXT_TS,
            replay_records=replay_records,
        )

    finally:
        c.find_stack_worker_result = old_find
        c._replay_stack_request_release_ts = old_release

    print("find calls:", len(calls))
    print("result:", result)
    print(
        "transport:",
        state.get("pending_stack_worker_requests"),
    )
    print(
        "candidate owner:",
        (
            state.get("pending_stack_reads")
            or {}
        ).get(SEAT, {}).get(
            "stack_worker_request_id"
        ),
    )

    # After the production fix, pre-capture collection and semantic
    # reconciliation are atomic at a due settled-stack boundary.
    #
    # The collector performs the only worker-result lookup on this pass.
    # Because it missed the result, replay must hold without performing a
    # second physical lookup that could authorize advancement before semantic
    # reconciliation.
    assert len(calls) == 1, (
        "replay pre-capture performed an unexpected second "
        "worker-result lookup after collection"
    )

    assert result["reconciled"] is False, (
        "fixture unexpectedly reconciled a result that "
        "was absent during collection"
    )

    assert result["advance"] is False, (
        "RED: replay advanced when a boundary-owned "
        "stack result appeared after collection but before "
        "the semantic barrier. The result physically existed "
        "but had never been semantically reconciled."
    )

    assert (
        REQUEST_ID
        in state["pending_stack_worker_requests"]
    ), (
        "unreconciled result lost durable transport ownership"
    )

    assert (
        state["pending_stack_reads"][SEAT][
            "stack_worker_request_id"
        ]
        == REQUEST_ID
    ), (
        "candidate lost exact request ownership"
    )

    print(
        "PASS replay holds boundary when result arrives "
        "between collector and barrier"
    )


if __name__ == "__main__":
    main()
