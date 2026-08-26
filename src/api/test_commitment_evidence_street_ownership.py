from dataclasses import dataclass, field

from src.api.api_event_coordinator import (
    commitment_evidence_street,
    stamp_bet_region_street_ownership,
)
from src.observer.continuous_observer import (
    observations_from_changes,
)
from src.observer.observation_types import (
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
)


@dataclass
class Changes:
    stack_change_details: dict = field(
        default_factory=dict
    )
    bet_region_appeared: list = field(
        default_factory=list
    )
    bet_region_cleared: list = field(
        default_factory=list
    )
    bet_region_transitions: dict = field(
        default_factory=dict
    )


def main():
    seat = "synthetic_seat"

    # --------------------------------------------------------
    # Existing physical candidate outranks newer board-local
    # street attribution.
    # --------------------------------------------------------

    state = {
        "phase": "TURN",
        "pending_stack_reads": {
            seat: {
                "origin_street": "TURN",
            }
        },
        "bet_region_street_owners": {},
    }

    appeared = Changes(
        bet_region_appeared=[seat],
    )

    resolved = commitment_evidence_street(
        state,
        appeared,
        seat,
        "RIVER",
    )

    assert resolved == "TURN", resolved

    stamp_bet_region_street_ownership(
        state,
        appeared,
        "RIVER",
    )

    assert (
        appeared.bet_region_transitions[seat][
            "origin_street"
        ]
        == "TURN"
    )

    assert (
        state["bet_region_street_owners"][seat]
        == "TURN"
    )

    observations = observations_from_changes(
        appeared,
        street="RIVER",
    )

    occupied = [
        item
        for item in observations
        if item.type == BET_REGION_OCCUPIED
    ]

    assert len(occupied) == 1
    assert occupied[0].street == "TURN"

    # --------------------------------------------------------
    # After the stack candidate is gone, the active physical
    # bet-region lifecycle still owns its original street.
    # --------------------------------------------------------

    state["pending_stack_reads"] = {}

    cleared = Changes(
        bet_region_cleared=[seat],
    )

    stamp_bet_region_street_ownership(
        state,
        cleared,
        "RIVER",
    )

    observations = observations_from_changes(
        cleared,
        street="RIVER",
    )

    clear_items = [
        item
        for item in observations
        if item.type == BET_REGION_CLEARED
    ]

    assert len(clear_items) == 1
    assert clear_items[0].street == "TURN"

    # --------------------------------------------------------
    # With no physical owner, a genuinely new transition uses
    # the frame-local street normally.
    # --------------------------------------------------------

    fresh_state = {
        "phase": "TURN",
        "pending_stack_reads": {},
        "bet_region_street_owners": {},
    }

    fresh = Changes(
        bet_region_appeared=[seat],
    )

    stamp_bet_region_street_ownership(
        fresh_state,
        fresh,
        "RIVER",
    )

    assert (
        fresh.bet_region_transitions[seat][
            "origin_street"
        ]
        == "RIVER"
    )

    print(
        "PASS: one physical commitment retains one immutable "
        "street while genuinely new evidence uses frame-local street"
    )


if __name__ == "__main__":
    main()
