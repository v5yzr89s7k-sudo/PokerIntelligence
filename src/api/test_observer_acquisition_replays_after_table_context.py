"""
v0.16 buffered observer-acquisition replay contract.

An observer_acquisition event may arrive after local hand ownership begins
but before table_context has built CanonicalHand.

That event must survive bootstrap and be replayed immediately after
table_context establishes canonical structure.

Roster recovery and chronology acquisition remain separate concepts.
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
        hand_id="acquisition-table-context-replay",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

    return hand


def main():
    sm.reset_tracker()

    state = sm.default_state()

    state.update({
        "phase": "PREFLOP",
        "hero_cards": ["Qd", "7c"],
        "hand_started_at": 1.0,
        "hand_token": "hand-a",
        "canonical_snapshot_ready": False,
        "level": {},
    })

    acquisition = {
        "type": "observer_acquisition",
        "hand_token": "hand-a",
        "street": "PREFLOP",
        "visible_seats": [
            "co",
            "btn",
            "sb",
        ],
        "hero_owned": True,
        "ts": 1.1,
    }

    # First prove the event is buffered.
    state = sm.handle_event(
        state,
        acquisition,
    )

    pending = state.get(
        "pending_observer_acquisition_events"
    ) or []

    assert len(pending) == 1

    canonical = make_canonical()

    table_context = {
        "type": "table_context",
        "hand_token": "hand-a",
        "dealt_in_seats": list(POSITIONS),
        "positions": dict(POSITIONS),
        "dealer_button_seat": "btn",
        "hero_position": "BB",
        "participant_frame_count": 5,
        "players": [
            {
                "seat": seat,
                "name": seat.upper(),
                "stack_bb": 100.0,
                "stack_confidence": 1.0,
                "is_hero": seat == "hero",
                "is_active": True,
            }
            for seat in POSITIONS
        ],
        "ts": 1.2,
    }

    saved = []

    # Keep this contract focused on replay ownership rather than
    # CanonicalHand construction internals.
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
        state = sm.handle_table_context(
            state,
            table_context,
        )

    # Buffered acquisition must have been consumed.
    assert state.get(
        "pending_observer_acquisition_events"
    ) == [], (
        "buffered observer acquisition survived table_context "
        "instead of replaying"
    )

    # And its chronology frontier must now be authoritative.
    assert canonical.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ], canonical.players_to_act

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

    # No predecessor action semantics may appear.
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

    print(
        "PASS buffered observer acquisition replay: "
        "table_context activates chronology ownership without "
        "fabricating predecessor actions"
    )


if __name__ == "__main__":
    main()
