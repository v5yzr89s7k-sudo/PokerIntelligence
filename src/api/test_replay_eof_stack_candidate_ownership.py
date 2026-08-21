from src.api import api_event_coordinator as c


def main():
    state = c.fresh_state()

    # Real July 22 EOF shape: canonical hand has ended, coordinator is WAITING,
    # and visual cleanup creates a tokenless post-hand stack candidate.
    state["phase"] = "WAITING"
    state["hand_token"] = None
    state["pending_stack_reads"] = {
        "seat_lower_left": {
            "origin_street": "RIVER",
            "trigger_sources": [
                "bet_region_appeared",
                "stack_motion",
            ],
        },
    }

    assert (
        c.replay_pending_stack_candidates(state)
        == {}
    ), (
        "tokenless post-hand candidate must not "
        "block deterministic replay EOF"
    )

    # During an owned hand, the same physical candidate is legitimate finite
    # prerecorded work and must participate in EOF settlement.
    state["phase"] = "FLOP"
    state["hand_token"] = "hand-1"
    state["pending_stack_reads"] = {
        "seat_lower_left": {
            "hand_token": "hand-1",
            "origin_street": "FLOP",
            "trigger_sources": [
                "bet_region_appeared",
            ],
        },
    }

    owned = c.replay_pending_stack_candidates(
        state
    )

    assert (
        set(owned)
        == {"seat_lower_left"}
    ), owned

    print(
        "PASS replay EOF stack ownership: "
        "hand-owned prerecorded quantitative work drains, "
        "tokenless post-hand noise cannot block EOF"
    )


if __name__ == "__main__":
    main()
