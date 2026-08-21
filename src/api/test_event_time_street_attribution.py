from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import src.api.api_event_coordinator as coordinator


def changes(
    *,
    board_count,
    appeared=None,
    stack_changed=None,
):
    return SimpleNamespace(
        board_count=board_count,
        bet_region_appeared=list(appeared or []),
        stack_changed_seats=list(stack_changed or []),
        stack_change_details={},
    )


def main():
    # --------------------------------------------------------
    # Pure resolver.
    # --------------------------------------------------------

    preflop = {
        "phase": "PREFLOP",
    }

    assert (
        coordinator.event_street_for_frame(
            preflop,
            0,
        )
        == "PREFLOP"
    )

    # Partial board noise must not advance the street.
    assert (
        coordinator.event_street_for_frame(
            preflop,
            1,
        )
        == "PREFLOP"
    )

    assert (
        coordinator.event_street_for_frame(
            preflop,
            2,
        )
        == "PREFLOP"
    )

    assert (
        coordinator.event_street_for_frame(
            preflop,
            3,
        )
        == "FLOP"
    )

    assert (
        coordinator.event_street_for_frame(
            {"phase": "FLOP"},
            4,
        )
        == "TURN"
    )

    assert (
        coordinator.event_street_for_frame(
            {"phase": "TURN"},
            5,
        )
        == "RIVER"
    )

    # Never move event attribution backward.
    assert (
        coordinator.event_street_for_frame(
            {"phase": "FLOP"},
            0,
        )
        == "FLOP"
    )

    # --------------------------------------------------------
    # Replay 0001 semantic boundary:
    #
    # Existing Hero candidate began preflop. It must remain
    # PREFLOP after the local flop appears.
    #
    # New BB candidate beginning with board_count=3 must be FLOP.
    # --------------------------------------------------------

    state = {
        "phase": "PREFLOP",
        "pending_stack_reads": {
            "hero": {
                "first_change_ts": 1.0,
                "last_change_ts": 9999999999.0,
                "max_mean_diff": 0.0,
                "origin_street": "PREFLOP",
                "trigger_sources": [
                    "stack_motion",
                ],
            },
        },
    }

    frame = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    flop_event_street = (
        coordinator.event_street_for_frame(
            state,
            3,
        )
    )

    assert flop_event_street == "FLOP"

    with (
        patch.object(
            coordinator,
            "_canonical_stack_values",
            return_value={},
        ),
        patch.object(
            coordinator.time,
            "time",
            return_value=2.0,
        ),
    ):
        coordinator.enrich_stack_change_measurements(
            changes(
                board_count=3,
                appeared=[
                    "seat_mid_left",
                ],
            ),
            frame,
            state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            event_street=flop_event_street,
        )

    pending = state["pending_stack_reads"]

    assert pending["hero"]["origin_street"] == "PREFLOP"
    assert (
        pending["seat_mid_left"]["origin_street"]
        == "FLOP"
    )

    # --------------------------------------------------------
    # Old-street obligation boundary:
    #
    # A locally visible next street must not steal commitment
    # evidence from a seat that still owes action on the
    # confirmed old street.
    # --------------------------------------------------------

    turn_state = {
        "phase": "TURN",
        "pending_stack_reads": {},
    }

    river_event_street = (
        coordinator.event_street_for_frame(
            turn_state,
            5,
        )
    )

    assert river_event_street == "RIVER"

    with (
        patch.object(
            coordinator,
            "_canonical_stack_values",
            return_value={},
        ),
        patch.object(
            coordinator.time,
            "time",
            return_value=3.0,
        ),
    ):
        coordinator.enrich_stack_change_measurements(
            changes(
                board_count=5,
                appeared=[
                    "seat_lower_left",
                    "seat_mid_left",
                ],
            ),
            frame,
            turn_state,
            prior_occupied_bet_regions=set(),
            prior_commitment_seats=set(),
            event_street=river_event_street,
            old_street_owing_seats={
                "seat_lower_left",
            },
        )

    turn_pending = turn_state[
        "pending_stack_reads"
    ]

    assert (
        turn_pending["seat_lower_left"][
            "origin_street"
        ]
        == "TURN"
    )

    assert (
        turn_pending["seat_mid_left"][
            "origin_street"
        ]
        == "RIVER"
    )

    print(
        "PASS event-time street attribution: "
        "late Hero settlement remains PREFLOP; "
        "new BB commitment on local board=3 starts FLOP; "
        "old-street owing seat remains on confirmed street"
    )


if __name__ == "__main__":
    main()
