from types import SimpleNamespace

import src.api.api_event_coordinator as c


def main():
    seat = "seat_top"

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {},
        "bet_region_street_owners": {},
        "pending_boundary_route": {
            "hand_token": "test-hand",
            "previous_street": "PREFLOP",
            "next_street": "FLOP",
            "old_street_owing_seats": [seat],
        },
        "hand_token": "test-hand",
    }

    changes = SimpleNamespace(
        stack_change_details={},
        bet_region_appeared=[seat],
    )

    assert seat not in state["pending_stack_reads"]

    observed = c.commitment_evidence_street(
        state,
        changes,
        seat,
        "FLOP",
        old_street_owing_seats={seat},
    )

    print("canonical_street:", state["phase"])
    print("physical_street:", "FLOP")
    print("existing_candidate:", False)
    print("fresh_bet_region_appearance:", True)
    print("old_street_owing:", [seat])
    print("observed_ownership:", observed)
    print("expected_ownership:", "FLOP")

    assert observed == "FLOP", (
        "RED: a brand-new independently observed FLOP commitment "
        "was incorrectly assigned to the authoritative old street: "
        f"{observed}"
    )

    print(
        "PASS: fresh next-street commitment owns its physical onset street"
    )


if __name__ == "__main__":
    main()
