from src.api import api_event_coordinator as c


HAND = "synthetic-hand"
SEAT = "seat_test"
REQUEST = "consumed-request"


def make_state():
    state = c.fresh_state()

    state["hand_token"] = HAND
    state["phase"] = "FLOP"

    # The worker request was already consumed from durable
    # transport, but the semantic candidate retained its local
    # request-id bookkeeping field.
    state[
        "pending_stack_worker_requests"
    ] = {}

    state[
        "pending_stack_reads"
    ] = {
        SEAT: {
            "hand_token": HAND,
            "first_change_ts": 99.0,
            "last_change_ts": 100.4,
            "last_stack_sample_ts": 100.0,
            "origin_street": "FLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "validation_attempts": 0,
            "stack_worker_request_id": REQUEST,
        }
    }

    return state


def main():
    state = make_state()

    outstanding = (
        c.replay_outstanding_transport(
            state
        )
    )

    ownership = (
        c.replay_pending_stack_candidates(
            state
        )
    )

    entry = state[
        "pending_stack_reads"
    ][SEAT]

    print(
        "candidate-local request id:",
        entry.get(
            "stack_worker_request_id"
        ),
    )

    print(
        "pending transport:",
        state.get(
            "pending_stack_worker_requests"
        ),
    )

    print(
        "outstanding transport:",
        outstanding,
    )

    print(
        "EOF ownership:",
        ownership,
    )

    assert outstanding == {}

    # replay_pending_stack_candidates() must reconcile the
    # stale candidate-local correlation against the durable
    # transport ledger.
    assert (
        "stack_worker_request_id"
        not in entry
    ), (
        "REGRESSION: stale candidate-local worker ID "
        "was not cleared after durable transport vanished"
    )

    assert (
        REQUEST
        not in (
            state.get(
                "pending_stack_worker_requests"
            )
            or {}
        )
    )

    # Clearing phantom transport ownership does NOT mean the
    # physical candidate itself disappears immediately.
    #
    # This candidate has not consumed its one legitimate EOF
    # terminal quantitative opportunity yet, so it may remain
    # finite semantic work. The key invariant is that it is no
    # longer pretending an asynchronous worker request exists.
    assert SEAT in ownership

    reconciled = ownership[SEAT]

    assert (
        "stack_worker_request_id"
        not in reconciled
    )

    assert (
        c.replay_outstanding_transport(
            state
        )
        == {}
    )

    print(
        "PASS stale candidate-local worker ID is "
        "reconciled without discarding legitimate finite "
        "EOF candidate work"
    )


if __name__ == "__main__":
    main()
