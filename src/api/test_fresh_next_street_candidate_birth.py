from unittest.mock import patch

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_top"


def main():
    state = c.fresh_state()
    state["hand_token"] = "fresh-next-street-birth-test"
    state["phase"] = "PREFLOP"

    assert not state["pending_stack_reads"]
    assert not state["bet_region_street_owners"]

    changes = ChangeSet()
    changes.board_count = 3
    changes.bet_region_appeared = [SEAT]
    changes.bet_region_transitions = {
        SEAT: {
            "appeared": True,
            "previous_occupied": False,
            "current_occupied": True,
        }
    }

    # Exact ownership shape of the Sept. 6 divergence:
    #
    # canonical still PREFLOP,
    # local/physical street already FLOP,
    # canonical owing still contains this seat,
    # but there is no pre-existing physical candidate or
    # bet-region lifecycle owner tying this new onset to PREFLOP.
    with patch.object(
        c,
        "_canonical_stack_values",
        return_value={},
    ):
        c.enrich_stack_change_measurements(
            changes,
            None,
            state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            response_to_aggression_seats=set(),
            event_street="FLOP",
            old_street_owing_seats={SEAT},
            recent_stack_observations=None,
            frame_path="/tmp/fresh_flop.png",
            frame_ts=100.0,
            stack_worker_results={},
            queue_stack_ocr=False,
        )

    candidate = (
        state.get("pending_stack_reads")
        or {}
    ).get(SEAT)

    print("candidate:", candidate)

    assert candidate is not None, (
        "fixture failed to create fresh FLOP stack candidate"
    )

    assert (
        str(candidate.get("origin_street") or "").upper()
        == "FLOP"
    ), (
        "REGRESSION: fresh FLOP candidate inherited PREFLOP "
        "solely from stale canonical owing"
    )

    # Exercise the physical bet-region ownership path as well.
    c.stamp_bet_region_street_ownership(
        state,
        changes,
        "FLOP",
        old_street_owing_seats={SEAT},
    )

    owner = (
        state.get("bet_region_street_owners")
        or {}
    ).get(SEAT)

    transition_street = (
        changes.bet_region_transitions
        .get(SEAT, {})
        .get("origin_street")
    )

    print("bet owner:", owner)
    print("transition street:", transition_street)

    assert owner == "FLOP", owner
    assert transition_street == "FLOP", transition_street

    print(
        "PASS: fresh next-street commitment is born FLOP "
        "through candidate and bet-owner production paths"
    )


if __name__ == "__main__":
    main()
