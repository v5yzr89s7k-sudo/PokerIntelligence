"""
v0.16 observer-acquisition event state-machine contract.

The coordinator supplies neutral same-hand visibility:

    observer_acquisition {
        hand_token,
        street,
        visible_seats,
        hero_owned,
        ts
    }

The state machine owns persistence and canonical admission.
BettingRoundTracker alone converts visibility into legal queue ownership.
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
        hand_id="observer-acquisition-event",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

    return hand


def acquisition_event(token="hand-a"):
    return {
        "type": "observer_acquisition",
        "hand_token": token,
        "street": "PREFLOP",
        "visible_seats": [
            "co",
            "btn",
            "sb",
        ],
        "hero_owned": True,
        "ts": 10.0,
    }


def main():
    sm.reset_tracker()

    # --------------------------------------------------------------
    # RED 1:
    # Evidence arriving before canonical bootstrap must survive.
    # --------------------------------------------------------------
    state = sm.default_state()

    state["phase"] = "PREFLOP"
    state["hand_token"] = "hand-a"
    state["canonical_snapshot_ready"] = False

    state = sm.handle_event(
        state,
        acquisition_event(),
    )

    pending = state.get(
        "pending_observer_acquisition_events"
    ) or []

    assert len(pending) == 1, (
        "observer acquisition was lost before canonical bootstrap"
    )

    assert pending[0]["hand_token"] == "hand-a"
    assert pending[0]["visible_seats"] == [
        "co",
        "btn",
        "sb",
    ]

    # --------------------------------------------------------------
    # RED 2:
    # Once canonical exists, the event must establish the betting
    # ownership frontier without creating poker actions.
    # --------------------------------------------------------------
    canonical = make_canonical()

    state["canonical_snapshot_ready"] = True

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
            acquisition_event(),
        )

    assert canonical.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ], canonical.players_to_act

    voluntary = [
        action
        for action in canonical.actions
        if action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    assert voluntary == [], [
        (action.seat, action.action)
        for action in voluntary
    ]

    assert saved, (
        "frontier mutation was not persisted"
    )

    # --------------------------------------------------------------
    # RED 3:
    # Stale another-hand acquisition evidence cannot mutate this hand.
    # --------------------------------------------------------------
    before = list(canonical.players_to_act)

    with (
        patch.object(
            sm,
            "canonical_load",
            return_value=canonical,
        ),
        patch.object(
            sm,
            "canonical_save",
        ),
    ):
        state = sm.handle_event(
            state,
            acquisition_event(
                token="old-hand"
            ),
        )

    assert canonical.players_to_act == before

    print(
        "PASS observer acquisition event state machine: "
        "buffered before bootstrap, admitted same-hand, stale rejected"
    )


if __name__ == "__main__":
    main()
