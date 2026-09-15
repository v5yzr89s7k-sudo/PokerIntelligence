"""
September 8 acquisition-frontier ownership regression.

Real replay order is:

    actor_observed(CO)
        BEFORE
    observer_acquisition(visible BTN)

Therefore CO is already same-hand owned chronology.

The later visibility event must not reclassify CO as pre-acquisition.
The earliest trustworthy same-hand chronology evidence wins.
"""

from unittest.mock import patch

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


POSITIONS = {
    "utg": "UTG",
    "lj": "LJ",
    "hj": "HJ",
    "co": "CO",
    "btn": "BTN",
    "sb": "SB",
    "hero": "BB",
}


def make_canonical():
    players = [
        {
            "seat": seat,
            "name": seat.upper(),
            "stack_bb": 100.0,
            "is_hero": seat == "hero",
            "is_active": True,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="actor-owned-frontier",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

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

    canonical = make_canonical()

    state = sm.default_state()

    state.update({
        "phase": "PREFLOP",
        "hand_token": "hand-a",
        "canonical_snapshot_ready": True,
    })

    # --------------------------------------------------------------
    # First trustworthy owned chronology evidence is CO.
    #
    # This must establish acquisition at CO without manufacturing
    # UTG/LJ/HJ actions.
    # --------------------------------------------------------------
    actor_event = {
        "type": "actor_observed",
        "hand_token": "hand-a",
        "street": "PREFLOP",
        "seat": "co",
        "source": "bet_region_appeared",
        "commitment_visible": True,
        "blocked_seats": [],
        "ts": 5.0,
    }

    saved = []

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=canonical,
        ),
        patch.object(
            sm,
            "canonical_save",
            side_effect=lambda hand, **kwargs: saved.append(hand),
        ),
    ):
        state = sm.handle_event(
            state,
            actor_event,
        )

    frontier = state.get(
        "observer_acquisition_frontier"
    ) or {}

    assert frontier.get(
        "first_owned_seat"
    ) == "co", frontier

    assert frontier.get(
        "pre_acquisition_seats"
    ) == [
        "utg",
        "lj",
        "hj",
    ], frontier

    assert canonical.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ], canonical.players_to_act

    # Acquisition classification is not a poker action.
    assert voluntary_actions(canonical) == [], [
        (action.seat, action.action)
        for action in voluntary_actions(canonical)
    ]

    # --------------------------------------------------------------
    # Later visibility begins at BTN.
    #
    # It must NOT move the already-established frontier forward and
    # discard CO.
    # --------------------------------------------------------------
    visibility_event = {
        "type": "observer_acquisition",
        "hand_token": "hand-a",
        "street": "PREFLOP",
        "visible_seats": [
            "btn",
        ],
        "hero_owned": True,
        "ts": 20.0,
    }

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=canonical,
        ),
        patch.object(
            sm,
            "canonical_save",
            side_effect=lambda hand, **kwargs: saved.append(hand),
        ),
    ):
        state = sm.handle_event(
            state,
            visibility_event,
        )

    frontier_after = state.get(
        "observer_acquisition_frontier"
    ) or {}

    assert frontier_after.get(
        "first_owned_seat"
    ) == "co", frontier_after

    assert frontier_after.get(
        "pre_acquisition_seats"
    ) == [
        "utg",
        "lj",
        "hj",
    ], frontier_after

    assert canonical.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ], canonical.players_to_act

    assert voluntary_actions(canonical) == []

    print(
        "PASS earliest owned chronology wins: "
        "CO actor_observed establishes frontier and later BTN "
        "visibility cannot move it forward"
    )


if __name__ == "__main__":
    main()
