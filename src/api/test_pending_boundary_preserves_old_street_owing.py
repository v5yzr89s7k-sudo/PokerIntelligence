"""
Generic physical-boundary ownership regression.

A local next street may become visible before the authoritative old betting
round is complete.

Once authoritative old-street owing seats are captured for that physical
boundary, subsequent frames on the same unresolved boundary must retain that
ownership. The set must not disappear merely because the boundary was opened
on an earlier frame.

No replay-specific cards, players, stack values, or frame numbers.
"""

import src.api.api_event_coordinator as c


def main():
    actor = "seat_test"
    token = "hand-test"

    state = c.fresh_state()
    state["phase"] = "TURN"
    state["hand_token"] = token

    # Model an already-open physical TURN -> RIVER boundary.
    #
    # The first boundary frame learned authoritatively that ACTOR still owed
    # TURN action. A later frame is still physically RIVER-visible while the
    # canonical state remains TURN.
    state["pending_boundary_route"] = {
        "hand_token": token,
        "previous_street": "TURN",
        "next_street": "RIVER",
        "frames": [],
        "required_event_cursor": None,
        "old_street_owing_seats": [actor],
    }

    assert hasattr(
        c,
        "pending_boundary_old_street_owing_seats",
    ), (
        "RED: coordinator has no generic accessor preserving authoritative "
        "old-street owing ownership across frames of the same unresolved "
        "physical boundary"
    )

    owing = c.pending_boundary_old_street_owing_seats(
        state,
        previous_street="TURN",
        next_street="RIVER",
    )

    print("owing:", sorted(owing))

    assert owing == {actor}, (
        "RED: unresolved physical boundary lost authoritative old-street "
        "owing ownership on a later frame"
    )

    # And prove that the retained ownership feeds the already-correct generic
    # commitment resolver.
    changes = type(
        "Changes",
        (),
        {
            "stack_change_details": {},
        },
    )()

    resolved = c.commitment_evidence_street(
        state,
        changes,
        actor,
        "RIVER",
        old_street_owing_seats=owing,
    )

    print("resolved:", resolved)

    assert resolved == "TURN", (
        "RED: retained boundary ownership failed to preserve canonical "
        "street attribution"
    )

    print(
        "PASS unresolved physical boundary preserves authoritative "
        "old-street owing ownership across frames"
    )


if __name__ == "__main__":
    main()
