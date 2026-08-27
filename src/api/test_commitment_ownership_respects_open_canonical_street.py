"""
Generic physical-commitment street ownership contract.

If local board visibility provisionally leads canonical state, a newly
appearing commitment from a player who still owes action on the authoritative
canonical street belongs to that canonical street.

No hand-specific cards, stack values, frame numbers, or player identities.
"""

from types import SimpleNamespace

import src.api.api_event_coordinator as c


ACTOR = "seat_test"
OLD_STREET = "TURN"
LOCAL_NEXT_STREET = "RIVER"


def main():
    state = c.fresh_state()
    state["phase"] = OLD_STREET
    state["hand_token"] = "test-hand"

    changes = SimpleNamespace(
        stack_change_details={},
    )

    old_street_owing_seats = {
        ACTOR,
    }

    print("canonical:", state["phase"])
    print("local fallback:", LOCAL_NEXT_STREET)
    print("owing:", sorted(old_street_owing_seats))

    # Exercise the actual production ownership resolver.
    #
    # There is deliberately:
    #   - no validated stack detail,
    #   - no existing stack candidate,
    #   - no existing bet-region owner.
    #
    # Therefore this models a genuinely NEW physical commitment appearing
    # while local board visibility is one street ahead.
    resolved = c.commitment_evidence_street(
        state,
        changes,
        ACTOR,
        LOCAL_NEXT_STREET,
        old_street_owing_seats=(
            old_street_owing_seats
        ),
    )

    print("production resolved:", resolved)

    assert resolved == OLD_STREET, (
        "RED: production assigned a newly appearing physical commitment "
        "to the locally visible next street even though this actor still "
        "owes action on the authoritative canonical street"
    )

    print(
        "PASS production preserves authoritative open-street "
        "physical-action ownership"
    )


if __name__ == "__main__":
    main()
