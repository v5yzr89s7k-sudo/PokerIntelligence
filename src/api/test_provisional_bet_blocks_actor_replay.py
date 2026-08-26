from unittest.mock import patch

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="provisional-actor-replay",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_lower_left",
                "name": "BB",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_lower_right",
                "name": "BTN",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "seat_lower_left": "BB",
            "seat_lower_right": "BTN",
        },
        started_ts=1.0,
    )

    hand.current_street = "FLOP"
    hand.players_to_act = [
        "hero",
        "seat_lower_left",
        "seat_lower_right",
    ]

    return hand


def main():
    hand = make_hand()

    state = {
        "phase": "FLOP",
        "canonical_snapshot_ready": True,
        "hand_token": "test-hand",
        "unresolved_stack_candidates": {},
        "unresolved_provisional_bets": {
            "FLOP:seat_lower_left": {
                "seat": "seat_lower_left",
                "street": "FLOP",
                "source": "transition",
                "bet_bb": 3.37,
            },
        },
        "pending_actor_observations": [],
        "pending_physical_actor_completions": [],
        "pending_inferred_actions": [],
    }

    later_actor = {
        "type": "actor_observed",
        "hand_token": "test-hand",
        "seat": "seat_lower_right",
        "street": "FLOP",
        "source": "physical_actor_completed",
        "ts": 10.0,
    }

    with patch.object(sm, "canonical_load", return_value=hand), \
         patch.object(sm, "canonical_save"):

        state = sm.handle_actor_observed(
            state,
            later_actor,
        )

    assert hand.players_to_act == [
        "hero",
        "seat_lower_left",
        "seat_lower_right",
    ], (
        "BUG: later actor crossed unresolved provisional bet; "
        f"queue={hand.players_to_act}"
    )

    assert not any(
        action.seat == "seat_lower_left"
        for action in hand.actions
    ), (
        "BUG: provisional-bet owner received fabricated passive action"
    )

    assert state["pending_actor_observations"], (
        "BUG: blocked later actor was not preserved for replay"
    )

    print(
        "PASS provisional bet blocks actor replay: "
        "later physical chronology cannot cross unresolved "
        "same-street provisional ownership"
    )


if __name__ == "__main__":
    main()
