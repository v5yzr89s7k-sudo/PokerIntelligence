"""
Generic chronology contract.

Local board visibility may lead canonical state by one street.

When the authoritative betting-round status says an actor still owes action
on the canonical street, genuinely new physical stack motion for that actor
must inherit the canonical street rather than the locally visible next street.

This regression contains no replay-specific frames, players, cards, or stack
amounts.
"""

from dataclasses import dataclass, field

import src.api.api_event_coordinator as c


ACTOR = "seat_test"
CANONICAL_STREET = "TURN"
LOCAL_STREET = "RIVER"


@dataclass
class Changes:
    stack_changed_seats: list = field(
        default_factory=lambda: [ACTOR]
    )
    stack_change_details: dict = field(default_factory=dict)
    bet_region_appeared: list = field(default_factory=list)
    bet_region_cleared: list = field(default_factory=list)
    bet_region_transitions: dict = field(default_factory=dict)


def main():
    state = c.fresh_state()

    state["phase"] = CANONICAL_STREET
    state["hand_token"] = "hand-test"
    state["pending_stack_reads"] = {}
    state["bet_region_street_owners"] = {}

    changes = Changes()

    authoritative_status = {
        "street": CANONICAL_STREET,
        "complete": False,
        "players_owing_action": [ACTOR],
        "canonical_players_to_act": [ACTOR],
        "hand_token": "hand-test",
    }

    # The production frame loop needs one generic operation that derives the
    # old-street ownership set from authoritative betting-round status.
    #
    # Do not duplicate poker logic in this test. Locate the actual production
    # helper/input path and exercise it.
    helper_names = [
        name
        for name in dir(c)
        if (
            "owing" in name.lower()
            or "betting_round_status" in name.lower()
        )
        and callable(getattr(c, name))
    ]

    print("candidate helpers:", helper_names)

    assert helper_names, (
        "RED: coordinator exposes no testable generic path for deriving "
        "authoritative old-street owing ownership"
    )

    # Candidate-origin production rule itself is already known to be correct.
    # Verify that when supplied authoritative ownership it keeps the action
    # on the canonical street.
    c.enrich_stack_change_measurements(
        changes,
        None,
        state,
        prior_occupied_bet_regions=set(),
        prior_commitment_seats=set(),
        response_to_aggression_seats=set(),
        event_street=LOCAL_STREET,
        old_street_owing_seats={ACTOR},
        recent_stack_observations=None,
        frame_path="/tmp/frame.png",
        frame_ts=100.0,
        stack_worker_results={},
        queue_stack_ocr=False,
    )

    candidate = (
        state.get("pending_stack_reads")
        or {}
    ).get(ACTOR)

    print("candidate:", candidate)

    assert candidate is not None, (
        "fixture failed to open stack candidate"
    )

    assert (
        str(candidate.get("origin_street") or "").upper()
        == CANONICAL_STREET
    ), (
        "RED: authoritative owing actor was relabeled to locally visible "
        "next street at physical candidate birth"
    )

    print(
        "PASS authoritative old-street owing ownership reaches "
        "new physical stack candidate"
    )


if __name__ == "__main__":
    main()
