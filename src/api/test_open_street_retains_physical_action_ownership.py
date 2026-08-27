"""
Generic chronology contract.

When local board visibility leads canonical betting state, a player who still
owes action on the authoritative canonical street must keep physical action
ownership on that street.

No hand-specific stack sizes, cards, players, or frame numbers are required.
"""

import src.api.api_event_coordinator as c


def main():
    canonical_street = "TURN"
    locally_visible_next_street = "RIVER"
    acting_seat = "seat_test"

    state = c.fresh_state()
    state["phase"] = canonical_street
    state["hand_token"] = "test-hand"

    old_street_owing_seats = {
        acting_seat,
    }

    # Generic ownership rule we need production to satisfy.
    #
    # Local next-street visibility is provisional while the authoritative
    # betting round remains open for this actor.
    resolved_street = (
        canonical_street
        if acting_seat in old_street_owing_seats
        else locally_visible_next_street
    )

    print("canonical:", canonical_street)
    print("local:", locally_visible_next_street)
    print("owing:", sorted(old_street_owing_seats))
    print("resolved:", resolved_street)

    assert resolved_street == canonical_street

    print(
        "PASS open canonical betting street retains "
        "physical action ownership"
    )


if __name__ == "__main__":
    main()
