from src.api import api_event_state_machine as sm


def main():
    # This regression isolates the July 22 TURN condition.
    #
    # The next street is physically confirmed. Both current-street actors
    # still owe action, but the only unresolved evidence for either seat is
    # raw stack motion. There is no independent chip-commitment evidence.
    #
    # Such a candidate is a perception hypothesis, not quantitative
    # commitment ownership, and must not veto passive boundary resolution.

    state = sm.default_state()

    state["phase"] = "TURN"
    state["hand_token"] = "boundary-motion-only-test"
    state["canonical_snapshot_ready"] = True

    state["unresolved_stack_candidates"] = {
        "TURN:hero": {
            "seat": "hero",
            "street": "TURN",
            "sources": [
                "stack_motion",
            ],
            "ts": 100.0,
        },
        "TURN:seat_lower_left": {
            "seat": "seat_lower_left",
            "street": "TURN",
            "sources": [
                "stack_motion",
            ],
            "ts": 100.1,
        },
    }

    ownership = sm.unresolved_board_ownership(
        state,
        "TURN",
    )

    print("ownership:", ownership)

    assert ownership["awaiting_action"] == []
    assert ownership["provisional_bets"] == []
    assert ownership["commitment_candidates"] == []
    assert ownership["blocked"] is False

    # The physical-completion arbitration already implements the same
    # evidence hierarchy. Motion-only candidates cannot veto trustworthy
    # passive physical chronology.
    assert not sm.physical_completion_stack_blocked(
        state,
        "TURN",
        "hero",
    )

    assert not sm.physical_completion_stack_blocked(
        state,
        "TURN",
        "seat_lower_left",
    )

    # Independent commitment evidence MUST continue to block.
    state["unresolved_stack_candidates"][
        "TURN:seat_lower_left"
    ]["sources"].append(
        "bet_region_appeared"
    )

    assert sm.physical_completion_stack_blocked(
        state,
        "TURN",
        "seat_lower_left",
    )

    ownership = sm.unresolved_board_ownership(
        state,
        "TURN",
    )

    print("ownership with commitment:", ownership)

    assert "seat_lower_left" in (
        ownership["commitment_candidates"]
    )

    assert ownership["blocked"] is True

    print(
        "PASS evidence hierarchy: raw stack motion is not "
        "commitment ownership; independent bet-region evidence is"
    )


if __name__ == "__main__":
    main()
