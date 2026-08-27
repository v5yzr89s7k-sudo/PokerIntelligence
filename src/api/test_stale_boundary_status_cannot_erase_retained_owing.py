"""
Generic boundary ownership freshness regression.

A pending physical boundary may already own an authoritative old-street
owing set established by an acknowledged state-machine status.

A later status artifact that matches hand/street but has not acknowledged
the boundary's required event cursor must not erase that retained ownership.

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
        "required_event_cursor": 20,
        "last_acknowledged_event_cursor": 18,
        "old_street_owing_seats": [ACTOR],
    }

    retained = c.pending_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
    )

    assert retained == {ACTOR}

    stale_status = {
        "hand_token": TOKEN,
        "street": "TURN",
        "processed_event_cursor": 19,
        "complete": False,
        "betting_open": True,
        "players_owing_action": [],
        "canonical_players_to_act": [],
    }

    assert hasattr(
        c,
        "refresh_boundary_old_street_owing_seats",
    ), (
        "RED: coordinator has no causal-freshness helper protecting retained "
        "boundary ownership from a stale matching status artifact"
    )

    resolved = c.refresh_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
        status=stale_status,
    )

    print("retained:", sorted(retained))
    print("stale status owing:", stale_status["players_owing_action"])
    print("resolved:", sorted(resolved))

    assert resolved == {ACTOR}, (
        "RED: stale hand/street-matching betting status erased previously "
        "acknowledged old-street boundary ownership"
    )

    fresh_status = dict(stale_status)
    fresh_status.update({
        "processed_event_cursor": 20,
        "complete": True,
        "betting_open": False,
        "players_owing_action": [],
        "canonical_players_to_act": [],
    })

    resolved_fresh = c.refresh_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
        status=fresh_status,
    )

    print("fresh completed resolved:", sorted(resolved_fresh))

    assert resolved_fresh == set(), (
        "fixture failed: causally fresh completed status must be allowed "
        "to clear retained old-street ownership"
    )

    print()
    print(
        "PASS only causally acknowledged status may replace "
        "retained physical-boundary owing ownership"
    )


if __name__ == "__main__":
    main()
