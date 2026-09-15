"""
Replay EOF ownership contract.

A trusted unchanged stack read may deliberately preserve its semantic
candidate while disarming automatic quantitative polling. During live
capture and ordinary replay that candidate must remain available for
fresh future commitment evidence to re-arm it.

At finite replay EOF there is no future perception frame. Therefore a
candidate that:

    - has no outstanding stack worker request,
    - has trusted_unchanged_polling_disarmed=True,

has no finite replay work remaining and must not block EOF completion.

The semantic candidate itself remains preserved in pending_stack_reads.
Only the replay-EOF blocking projection excludes it.
"""

from src.api import api_event_coordinator as c


SEAT = "seat_mid_left"


def main():
    state = c.fresh_state()

    state["hand_token"] = "synthetic-hand"

    state["pending_stack_reads"] = {
        SEAT: {
            "hand_token": "synthetic-hand",
            "first_change_ts": 100.0,
            "last_change_ts": 101.0,
            "sampling_floor_ts": 100.0,
            "sampling_floor_frame_path": "/tmp/0100_full.png",
            "max_mean_diff": 14.0,
            "origin_street": "WAITING",
            "trigger_sources": [
                "bet_region_appeared",
                "stack_motion",
            ],
            "unchanged_stack_reads": 1,
            "last_stack_sample_ts": 101.5,
            "trusted_unchanged_polling_disarmed": True,
        }
    }

    state["pending_stack_worker_requests"] = {}

    before = dict(
        state["pending_stack_reads"][SEAT]
    )

    candidates = (
        c.replay_pending_stack_candidates(
            state
        )
    )

    print(
        "EOF drain candidates:",
        candidates,
    )

    print(
        "candidate retained in state:",
        SEAT
        in state["pending_stack_reads"],
    )

    assert candidates == {}, (
        "RED: dormant trusted-unchanged candidate "
        "still blocks finite replay EOF"
    )

    assert (
        SEAT
        in state["pending_stack_reads"]
    ), (
        "EOF blocking projection deleted semantic "
        "candidate ownership"
    )

    assert (
        state["pending_stack_reads"][SEAT]
        == before
    ), (
        "EOF blocking projection mutated dormant "
        "semantic candidate"
    )

    print(
        "PASS replay EOF dormant trusted-unchanged "
        "candidate: semantic ownership is preserved "
        "but finite replay completion is not blocked"
    )


if __name__ == "__main__":
    main()
