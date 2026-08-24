from src.api import api_event_coordinator as c


SEAT = "hero"


def main():
    state = c.fresh_state()

    state["phase"] = "FLOP"
    state["hand_token"] = "synthetic-hand"

    # This is the exact lifecycle shape after:
    #
    #   1. a real physical stack candidate survives to EOF,
    #   2. EOF takes its one permitted terminal sample,
    #   3. the worker returns numeric evidence,
    #   4. continuity remains unresolved,
    #   5. worker ownership is cleared.
    #
    # The evidence remains unresolved and must not be promoted.
    # But there is no additional prerecorded quantitative work
    # left to drain.
    state["pending_stack_reads"] = {
        SEAT: {
            "hand_token": "synthetic-hand",
            "first_change_ts": 100.10,
            "last_change_ts": 100.40,
            "last_stack_sample_ts": 100.60,
            "origin_street": "FLOP",
            "trigger_sources": [
                "stack_motion",
            ],
            "validation_attempts": 0,
            "last_numeric_evidence_ts": 100.60,
            "last_numeric_evidence_reason": (
                "nearest_candidate_exceeds_drop_bound"
            ),
            "eof_terminal_sample_consumed": True,
        }
    }

    state["pending_stack_worker_requests"] = {}

    outstanding = c.replay_outstanding_transport(
        state
    )

    candidates = c.replay_pending_stack_candidates(
        state
    )

    print(
        "outstanding transport:",
        outstanding,
    )

    print(
        "EOF drain candidates:",
        candidates,
    )

    print(
        "candidate retained in state:",
        SEAT in state["pending_stack_reads"],
    )

    assert outstanding == {}

    # Critical distinction:
    #
    # pending_stack_reads is semantic candidate state.
    # replay_pending_stack_candidates is specifically the
    # inventory of candidates that STILL OWN FINITE
    # prerecorded quantitative work at EOF.
    #
    # Once the sole terminal sample has been consumed and
    # no request is outstanding, this candidate no longer
    # owns drainable work even though its unresolved evidence
    # may remain represented in coordinator state.
    assert SEAT not in candidates, (
        "REGRESSION REPRODUCED: EOF terminal sample was "
        "made single-use, but the consumed unresolved "
        "candidate still appears in replay_pending_stack_candidates; "
        "main() therefore resets the quiet timer forever "
        "even though no transport or prerecorded quantitative "
        "work remains"
    )

    print(
        "PASS consumed EOF terminal candidate no longer "
        "blocks replay drain"
    )


if __name__ == "__main__":
    main()
