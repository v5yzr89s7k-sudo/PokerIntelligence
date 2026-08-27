from unittest.mock import patch

from src.api import api_event_coordinator as c


def main():
    state = c.fresh_state()

    state["hand_token"] = "hand-test"
    state["phase"] = "TURN"

    state["pending_boundary_route"] = {
        "hand_token": "hand-test",
        "previous_street": "TURN",
        "next_street": "RIVER",
        "frames": [],
        "required_event_cursor": None,
        "old_street_owing_seats": [
            "seat_test",
        ],
    }

    entry = {
        "first_change_ts": 100.0,
        "last_change_ts": 100.0,
        "origin_street": "TURN",
        "trigger_sources": [
            "stack_motion",
        ],
        "unchanged_stack_reads": 999,
    }

    state["pending_stack_reads"] = {
        "seat_test": entry,
    }

    assert hasattr(
        c,
        "current_commitment_old_street_owing_seats",
    )

    owing = (
        c.current_commitment_old_street_owing_seats(
            state,
            previous_street="TURN",
            next_street="RIVER",
            fallback=[],
        )
    )

    print("candidate street:", entry["origin_street"])
    print("authoritative owing:", sorted(owing))
    print(
        "unchanged reads:",
        entry["unchanged_stack_reads"],
    )

    assert "seat_test" in owing

    # This is the missing production contract.
    #
    # A candidate that still owns action on the unresolved
    # authoritative street must not be retired merely because
    # trusted OCR continues to report the unchanged pre-action
    # stack before the displayed stack catches up.
    assert hasattr(
        c,
        "stack_candidate_must_remain_open_for_authoritative_owing",
    ), (
        "RED: coordinator has no generic candidate-lifetime "
        "guard preserving an unresolved physical candidate "
        "while its actor still authoritatively owes action "
        "on that candidate's own street"
    )

    keep_open = (
        c.stack_candidate_must_remain_open_for_authoritative_owing(
            state,
            "seat_test",
            entry,
            fallback_old_street_owing_seats=[],
            event_street="RIVER",
        )
    )

    print("must remain open:", keep_open)

    assert keep_open is True, (
        "RED: unchanged-read exhaustion can retire a "
        "candidate even though its actor still owes action "
        "on that candidate's authoritative street"
    )

    print(
        "PASS authoritative owing prevents premature "
        "unchanged-read candidate retirement"
    )


if __name__ == "__main__":
    main()
