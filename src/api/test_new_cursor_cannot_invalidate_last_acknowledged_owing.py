"""
Generic causal boundary-ownership regression.

An unresolved physical boundary may retain authoritative old-street owing
ownership established by an earlier acknowledged state-machine cursor.

Publishing new coordinator events can arm a newer required_event_cursor before
the state machine has acknowledged it. During that interval, the last
acknowledged owing ownership remains authoritative.

A newer required cursor means "wait for refresh"; it must not mean "forget the
last acknowledged ownership."

No replay-specific players, cards, stacks, or frame numbers.
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
        # Ownership was established at cursor 20.
        "last_acknowledged_event_cursor": 20,
        "old_street_owing_seats": [ACTOR],
        # Coordinator subsequently published something new.
        "required_event_cursor": 21,
    }

    # State-machine artifact has not consumed cursor 21 yet. It is therefore
    # not allowed to replace ownership, but the ownership established at 20
    # must remain usable.
    status = {
        "hand_token": TOKEN,
        "street": "TURN",
        "processed_event_cursor": 20,
        "complete": False,
        "betting_open": True,
        "players_owing_action": [],
        "canonical_players_to_act": [],
    }

    owing = c.refresh_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
        status=status,
    )

    print("last acknowledged:", 20)
    print("new required:", 21)
    print("status cursor:", 20)
    print("resolved owing:", sorted(owing))

    assert owing == {ACTOR}, (
        "RED: arming a newer event cursor invalidated old-street owing "
        "ownership that had already been established by an earlier ACK"
    )

    resolved_street = c.commitment_evidence_street(
        state,
        type(
            "Changes",
            (),
            {
                "stack_change_details": {},
            },
        )(),
        ACTOR,
        "RIVER",
        old_street_owing_seats=owing,
    )

    print("candidate street:", resolved_street)

    assert resolved_street == "TURN", (
        "RED: candidate birth lost the last acknowledged old-street "
        "ownership while waiting for a newer event-cursor ACK"
    )

    print()
    print(
        "PASS newly armed cursor waits for refresh without "
        "invalidating last acknowledged physical ownership"
    )


if __name__ == "__main__":
    main()
