from src.api import api_event_coordinator as c


SEAT = "hero"


def make_state():
    state = c.fresh_state()
    state["hand_token"] = "hand-1"
    state["phase"] = "TURN"

    # Physical RIVER visibility has arrived while canonical TURN
    # still owes Hero. This reproduces the unresolved boundary
    # ownership involved in the July 22 TURN regression.
    state["pending_boundary_route"] = {
        "hand_token": "hand-1",
        "previous_street": "TURN",
        "next_street": "RIVER",
        "old_street_owing_seats": [SEAT],
    }

    return state


def make_entry(*sources):
    return {
        "first_change_ts": 10.0,
        "last_change_ts": 10.0,
        "origin_street": "TURN",
        "trigger_sources": list(sources),
        "unchanged_stack_reads": 3,
        "validation_attempts": 0,
        "hand_token": "hand-1",
    }


def main():
    # ------------------------------------------------------------
    # Motion-only candidate.
    #
    # Canonical owing is NOT independent evidence that chips moved.
    # Once trusted quantitative reads have repeatedly shown no stack
    # change, raw stack motion alone must not acquire unlimited life
    # merely because the actor still owes canonical TURN action.
    # ------------------------------------------------------------
    state = make_state()
    motion_only = make_entry("stack_motion")

    motion_retained = (
        c.stack_candidate_must_remain_open_for_authoritative_owing(
            state,
            SEAT,
            motion_only,
            fallback_old_street_owing_seats={SEAT},
            event_street="RIVER",
        )
    )

    print(
        "motion-only authoritative retention:",
        motion_retained,
    )

    assert motion_retained is False, (
        "RED: canonical authoritative owing gives a "
        "stack-motion-only candidate unlimited semantic lifetime "
        "after repeated trusted unchanged stack reads"
    )

    # ------------------------------------------------------------
    # Independent commitment evidence.
    #
    # A bet-region appearance is real physical chip-commitment
    # evidence. Canonical owing may continue protecting this candidate
    # while quantitative settlement is unresolved.
    # ------------------------------------------------------------
    state = make_state()
    committed = make_entry(
        "stack_motion",
        "bet_region_appeared",
    )

    committed_retained = (
        c.stack_candidate_must_remain_open_for_authoritative_owing(
            state,
            SEAT,
            committed,
            fallback_old_street_owing_seats={SEAT},
            event_street="RIVER",
        )
    )

    print(
        "commitment-evidenced authoritative retention:",
        committed_retained,
    )

    assert committed_retained is True, (
        "REGRESSION: genuine bet-region commitment evidence "
        "lost authoritative old-street protection"
    )

    print(
        "PASS authoritative owing lifetime arbitration: "
        "motion-only noise cannot gain unlimited lifetime; "
        "independent commitment evidence remains protected"
    )


if __name__ == "__main__":
    main()
