"""
Generic same-frame ownership freshness regression.

A coordinator frame may begin with one old-street owing snapshot and then
reconcile/acknowledge newer authoritative boundary state before physical
commitment ownership is stamped.

Commitment attribution must use the current durable boundary ownership at
the point of attribution, not a stale local copy captured earlier in the
frame.

No replay-specific players, cards, stacks, or frame numbers.
"""

import src.api.api_event_coordinator as c


ACTOR = "seat_test"
TOKEN = "hand-test"


def main():
    state = c.fresh_state()

    state["hand_token"] = TOKEN
    state["phase"] = "TURN"

    # Simulate the frame-local snapshot captured before same-frame
    # reconciliation/ACK refresh.
    stale_frame_local_owing = set()

    # During the same coordinator iteration, authoritative boundary ownership
    # becomes available and is persisted durably.
    state["pending_boundary_route"] = {
        "hand_token": TOKEN,
        "previous_street": "TURN",
        "next_street": "RIVER",
        "frames": [],
        "required_event_cursor": None,
        "last_acknowledged_event_cursor": 20,
        "old_street_owing_seats": [ACTOR],
    }

    durable = c.pending_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
    )

    print(
        "stale frame-local owing:",
        sorted(stale_frame_local_owing),
    )
    print(
        "current durable owing:",
        sorted(durable),
    )

    assert durable == {ACTOR}

    assert hasattr(
        c,
        "current_commitment_old_street_owing_seats",
    ), (
        "RED: commitment attribution has no generic late-binding accessor "
        "for current durable old-street ownership after same-frame ACK/"
        "reconciliation"
    )

    current = c.current_commitment_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
        fallback=stale_frame_local_owing,
    )

    print(
        "late-bound owing:",
        sorted(current),
    )

    assert current == {ACTOR}, (
        "RED: commitment attribution used stale frame-local owing ownership "
        "instead of the boundary ownership established during the same frame"
    )

    changes = type(
        "Changes",
        (),
        {
            "stack_change_details": {},
        },
    )()

    street = c.commitment_evidence_street(
        state,
        changes,
        ACTOR,
        "RIVER",
        old_street_owing_seats=current,
    )

    print("resolved street:", street)

    assert street == "TURN", (
        "RED: same-frame authoritative boundary refresh did not reach "
        "physical commitment street attribution"
    )

    print()
    print(
        "PASS commitment attribution late-binds current "
        "durable boundary ownership"
    )


if __name__ == "__main__":
    main()
