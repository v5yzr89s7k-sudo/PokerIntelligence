"""
Generic boundary lifecycle regression.

Event-cursor acknowledgement means the state machine has processed the
coordinator's events through a known point. It does NOT mean the old betting
round has completed.

If authoritative acknowledged status still reports actors owing action on
the old street, the physical next-street boundary must retain old-street
ownership.

No replay-specific players, cards, stack values, or frame numbers.
"""

import src.api.api_event_coordinator as c


ACTOR = "seat_test"
TOKEN = "hand-test"


def main():
    state = c.fresh_state()

    state["hand_token"] = TOKEN
    state["phase"] = "TURN"

    state["pending_boundary_route"] = {
        "hand_token": TOKEN,
        "previous_street": "TURN",
        "next_street": "RIVER",
        "frames": [],
        "required_event_cursor": 10,
        "old_street_owing_seats": [ACTOR],
    }

    authoritative_status = {
        "hand_token": TOKEN,
        "street": "TURN",
        "processed_event_cursor": 10,
        "complete": False,
        "betting_open": True,
        "players_owing_action": [ACTOR],
        "canonical_players_to_act": [ACTOR],
    }

    original_loader = c.load_betting_round_status
    original_queue = c.maybe_queue_boundary_stack_request

    queued = []

    def fake_loader():
        return dict(authoritative_status)

    def fake_queue(
        state,
        *,
        previous_street,
        next_street,
        frames,
        status,
    ):
        queued.append(
            {
                "previous_street": previous_street,
                "next_street": next_street,
                "status": dict(status),
            }
        )
        return state, None

    try:
        c.load_betting_round_status = fake_loader
        c.maybe_queue_boundary_stack_request = fake_queue

        state, payload = c.maybe_route_acknowledged_boundary(
            state
        )

    finally:
        c.load_betting_round_status = original_loader
        c.maybe_queue_boundary_stack_request = original_queue

    pending = state.get("pending_boundary_route")

    print("payload:", payload)
    print("queued:", queued)
    print("pending:", pending)

    assert pending is not None, (
        "RED: event-cursor ACK retired physical boundary ownership even "
        "though authoritative old-street betting remained open"
    )

    assert (
        str(
            pending.get("previous_street")
            or ""
        ).upper()
        == "TURN"
    )

    assert set(
        pending.get("old_street_owing_seats")
        or []
    ) == {ACTOR}, (
        "RED: acknowledged open old street lost its authoritative owing set"
    )

    owing = c.pending_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
    )

    assert owing == {ACTOR}

    print()
    print(
        "PASS cursor ACK does not retire an authoritative "
        "still-open betting boundary"
    )


if __name__ == "__main__":
    main()
