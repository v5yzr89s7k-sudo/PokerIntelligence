from unittest.mock import patch

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="postflop-no-fabrication",
        players=[
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 40.0,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 60.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "co": "CO",
            "btn": "BTN",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    # We are testing one authority rule only:
    # observing BTN later on an owned FLOP must not manufacture CO CHECK.
    hand.current_street = "FLOP"
    hand.current_bet_bb = 0.0
    hand.players_to_act = [
        "co",
        "btn",
        "hero",
    ]

    return hand


def main():
    canonical = make_hand()

    state = sm.default_state()
    state["hand_token"] = "postflop-no-fabrication"
    state["phase"] = "FLOP"
    state["canonical_snapshot_ready"] = True

    # Acquisition is already owned from CO forward.
    #
    # This test is NOT about discovering where observation began.
    # It isolates the separate production rule that currently allows a
    # later postflop actor to manufacture CHECK for an earlier owned seat.
    state["observer_acquisition_frontier"] = {
        "street": "FLOP",
        "first_owned_seat": "co",
        "pre_acquisition_seats": [],
        "owned_queue": [
            "co",
            "btn",
            "hero",
        ],
        "ts": 2.0,
    }

    saved = []

    def fake_load():
        return canonical

    def fake_save(hand, state=None):
        saved.append(hand)

    tracker = sm.tracker_for_hand(canonical)

    # This is the exact condition currently used by production to justify
    # manufacturing the predecessor CHECK.
    tracker.observed_street_start_owned = True
    tracker.has_open_bet = False

    before_queue = list(canonical.players_to_act)
    before_actions = list(canonical.actions)

    event = {
        "type": "actor_observed",
        "hand_token": state["hand_token"],
        "street": "FLOP",
        "seat": "btn",
        "ts": 10.0,
        "source": "actor_observed",
        "commitment_visible": False,
    }

    with (
        patch.object(
            sm,
            "canonical_load",
            side_effect=fake_load,
        ),
        patch.object(
            sm,
            "canonical_save",
            side_effect=fake_save,
        ),
    ):
        state = sm.handle_actor_observed(
            state,
            event,
            preserve_if_blocked=True,
        )

    predecessor_actions = [
        action
        for action in canonical.actions
        if (
            str(action.street or "").upper() == "FLOP"
            and action.seat == "co"
        )
    ]

    timeline_predecessors = [
        item
        for item in (
            state.get("action_timeline")
            or []
        )
        if (
            str(item.get("street") or "").upper()
            == "FLOP"
            and item.get("seat") == "co"
            and item.get("status")
            in {
                "OBSERVED",
                "CONFIRMED",
                "REFINED",
            }
        )
    ]

    print("before_queue:", before_queue)
    print(
        "after_queue:",
        canonical.players_to_act,
    )
    print(
        "canonical_predecessor_actions:",
        [
            (
                action.seat,
                action.action,
            )
            for action in predecessor_actions
        ],
    )
    print(
        "timeline_predecessors:",
        timeline_predecessors,
    )

    assert predecessor_actions == [], (
        "RED: later postflop actor manufactured "
        "canonical predecessor action"
    )

    assert timeline_predecessors == [], (
        "RED: later postflop actor manufactured "
        "ActionTimeline predecessor ownership"
    )

    assert "co" in canonical.players_to_act, (
        "RED: later postflop actor consumed "
        "unresolved predecessor obligation"
    )

    print(
        "PASS: later postflop actor cannot author "
        "predecessor CHECK or consume predecessor chronology"
    )


if __name__ == "__main__":
    main()
