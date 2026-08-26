from unittest.mock import patch

import src.api.api_event_coordinator as c


HAND = "synthetic-hand"
STREET = "FLOP"
NEXT = "TURN"
HERO = "hero"
OTHER = "seat_lower_left"


def boundary_seats(status):
    state = c.fresh_state()
    state["hand_token"] = HAND
    state["phase"] = STREET

    frames = [{
        "ts": 1000.0,
        "frame_path": "/tmp/0001_full.png",
        "local_board_count": 4,
    }]

    queued = []

    with patch.object(
        c,
        "append_jsonl",
        side_effect=lambda path, payload: queued.append(
            dict(payload)
        ),
    ):
        state, payload = c.maybe_queue_boundary_stack_request(
            state,
            previous_street=STREET,
            next_street=NEXT,
            frames=frames,
            status=status,
        )

    return (
        list(payload.get("seats") or [])
        if payload
        else []
    )


def main():
    # --------------------------------------------------------
    # This models the stale status visible BEFORE a completed
    # old-street quantitative action has been reconciled.
    # --------------------------------------------------------
    before_reconciliation = {
        "hand_token": HAND,
        "street": STREET,
        "players_owing_action": [
            HERO,
            OTHER,
        ],
    }

    # --------------------------------------------------------
    # This models the authoritative status immediately AFTER
    # that ready quantitative result is reconciled.
    #
    # Hero's old-street obligation has been consumed.
    # --------------------------------------------------------
    after_reconciliation = {
        "hand_token": HAND,
        "street": STREET,
        "players_owing_action": [
            OTHER,
        ],
    }

    stale = boundary_seats(
        before_reconciliation
    )

    reconciled = boundary_seats(
        after_reconciliation
    )

    print("stale boundary seats:", stale)
    print("reconciled boundary seats:", reconciled)

    assert stale != reconciled, (
        "HARNESS INVALID: statuses did not produce "
        "different ownership"
    )

    # The architectural invariant we are about to enforce:
    # boundary ownership must reflect reconciled old-street
    # obligations, never the stale pre-reconciliation snapshot.
    assert reconciled == [OTHER], reconciled

    print(
        "PASS fixture: ready old-street reconciliation "
        "changes boundary ownership"
    )

    # Physical street detection may preserve the boundary,
    # but it may no longer select authoritative owing seats
    # directly. That selection is acknowledgement-gated after
    # ready old-street quantitative reconciliation.
    source = open(
        "src/api/api_event_coordinator.py"
    ).read()

    loop_anchor = source.find(
        "boundary_frame_buffer.append({"
    )

    reconcile_anchor = source.find(
        'frame_timings["stack_reconciliation"]',
        loop_anchor,
    )

    assert loop_anchor >= 0
    assert reconcile_anchor >= 0

    pre_reconcile = source[
        loop_anchor:reconcile_anchor
    ]

    # Direct retrospective boundary routing must be absent
    # from the pre-reconciliation street-boundary section.
    assert (
        "state, _ = maybe_queue_boundary_stack_request("
        not in pre_reconcile
    )

    assert "pending_boundary_route" in pre_reconcile

    assert (
        "collect_ready_stack_worker_results("
        in pre_reconcile
    )

    assert (
        "process_stack_change_measurements_async("
        in pre_reconcile
    )

    # The routing helper itself must require the event cursor.
    helper_start = source.find(
        "def maybe_route_acknowledged_boundary("
    )

    helper_end = source.find(
        "\ndef ",
        helper_start + 1,
    )

    assert helper_start >= 0

    helper_source = source[
        helper_start:
        (
            helper_end
            if helper_end >= 0
            else len(source)
        )
    ]

    assert "processed_event_cursor" in helper_source
    assert "required_event_cursor" in helper_source

    print(
        "PASS: physical boundary ownership is no longer "
        "frozen before ready old-street reconciliation; "
        "authoritative routing is event-cursor ACK gated"
    )



if __name__ == "__main__":
    main()
