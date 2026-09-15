"""
Safety contract:

Observed physical commitment evidence is not permission to invent poker
semantics or sizing.

If a player is observed entering a commitment episode but:
    - no trusted stack delta exists,
    - no bet-amount result exists,
    - no other independent semantic evidence resolves the action,

then the canonical hand must not manufacture BET/CALL/RAISE or a numeric
amount merely to advance chronology.
"""

from unittest.mock import patch

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    players = [
        {
            "seat": "co",
            "name": "CO",
            "stack_bb": 39.27,
            "is_hero": False,
            "is_active": True,
        },
        {
            "seat": "btn",
            "name": "BTN",
            "stack_bb": 92.0,
            "is_hero": False,
            "is_active": True,
        },
        {
            "seat": "sb",
            "name": "SB",
            "stack_bb": 13.39,
            "is_hero": False,
            "is_active": True,
        },
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 12.92,
            "is_hero": True,
            "is_active": True,
        },
    ]

    hand = CanonicalHand().start_hand(
        hand_id="unresolved-commitment-no-fabrication",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "co": "CO",
            "btn": "BTN",
            "sb": "SB",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        "co",
        "btn",
        "sb",
        "hero",
    ]

    hand.current_street = "PREFLOP"
    hand.players_to_act = [
        "co",
        "btn",
        "sb",
        "hero",
    ]

    return hand


def voluntary_actions(hand):
    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    return [
        action
        for action in hand.actions
        if action.action not in forced
    ]


def main():
    sm.reset_tracker()

    hand = make_hand()

    state = sm.default_state()

    state.update({
        "phase": "PREFLOP",
        "hand_token": "hand-a",
        "canonical_snapshot_ready": True,
        "observer_acquisition_frontier": {
            "street": "PREFLOP",
            "first_owned_seat": "co",
            "pre_acquisition_seats": [],
            "owned_queue": [
                "co",
                "btn",
                "sb",
                "hero",
            ],
            "ts": 1.0,
        },
    })

    event = {
        "type": "actor_observed",
        "hand_token": "hand-a",
        "street": "PREFLOP",
        "seat": "co",
        "source": "bet_region_appeared",
        "commitment_visible": True,
        "blocked_seats": [],
        "ts": 2.0,
    }

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=hand,
        ),
        patch.object(
            sm,
            "canonical_save",
            return_value=None,
        ),
    ):
        state = sm.handle_event(
            state,
            event,
        )

    actions = voluntary_actions(hand)

    assert actions == [], (
        "RED: unresolved physical commitment manufactured "
        f"canonical action(s): "
        f"{[(a.seat, a.action, a.amount_bb) for a in actions]}"
    )

    assert hand.players_to_act[0] == "co", (
        "RED: unresolved CO commitment was consumed merely "
        "to advance chronology"
    )

    print(
        "PASS unresolved commitment safety: "
        "physical evidence preserved without fabricated "
        "BET/CALL/RAISE or forced chronology advance"
    )


if __name__ == "__main__":
    main()
