"""
September 8 live regression.

Observed ground truth:
    1. seat_top bet_region_appeared
    2. no validated stack transition
    3. no quantitative bet confirmation
    4. seat_top cards later disappeared

Required behavior:
    - step 1 may affect chronology/provisional perception
    - step 1 must NOT create durable betting action
    - step 4 must remain capable of resolving the seat as FOLD
"""

from unittest.mock import patch

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)


TOKEN = "sep8-false-seat-top"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="sep8-false-seat-top-hand",
        players=[
            {
                "seat": "seat_top",
                "name": "CO",
                "stack_bb": 39.27,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 12.92,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "seat_top": "CO",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.players_to_act = [
        "seat_top",
        "hero",
    ]

    return hand


def main():
    sm.reset_tracker()

    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["physical_street"] = "PREFLOP"
    state["canonical_snapshot_ready"] = True
    state["hand_token"] = TOKEN

    false_visual = {
        "type": "actor_observed",
        "hand_token": TOKEN,
        "seat": "seat_top",
        "street": "PREFLOP",
        "source": "bet_region_appeared",
        "commitment_visible": True,
        "blocked_seats": [],
        "ts": 10.0,
    }

    card_disappearance = {
        "type": "physical_actor_completed",
        "hand_token": TOKEN,
        "seat": "seat_top",
        "street": "PREFLOP",
        "source": "opponent_card_disappearance",
        "evidence": [
            "opponent_cards_visible_before",
            "opponent_cards_absent_after",
            "calibrated_acr_card_back",
        ],
        "ts": 26.3,
    }

    with patch.object(
        sm,
        "canonical_load",
        return_value=hand,
    ), patch.object(
        sm,
        "canonical_save",
    ), patch.object(
        sm,
        "tracker_for_hand",
        return_value=tracker,
    ), patch.object(
        sm,
        "refresh_live_presentation",
        side_effect=lambda state: state,
    ), patch.object(
        sm,
        "write_betting_round_status",
    ):

        state = sm.handle_actor_observed(
            state,
            false_visual,
        )

        timeline_after_visual = list(
            state.get("action_timeline")
            or []
        )

        print(
            "timeline_after_false_visual:",
            timeline_after_visual,
        )

        assert not any(
            item.get("seat") == "seat_top"
            and str(
                item.get("action") or ""
            ).upper()
            in {
                "BET",
                "RAISE",
                "BET_OR_RAISE",
                "CALL_OR_RAISE",
                "COMMITMENT",
            }
            for item in timeline_after_visual
        ), (
            "RED: raw seat_top bet-region appearance "
            "created durable betting ownership before "
            "independent corroboration"
        )

        state = sm.handle_physical_actor_completed(
            state,
            card_disappearance,
        )

    actions = [
        (
            action.seat,
            action.action,
        )
        for action in hand.actions
    ]

    print("canonical_actions:", actions)

    assert (
        "seat_top",
        "FOLD",
    ) in actions, (
        "RED: later card disappearance did not "
        "resolve uncorroborated visual hypothesis as FOLD"
    )

    print(
        "PASS: uncorroborated bet-region appearance "
        "remains provisional and later card disappearance "
        "resolves the actual fold"
    )


if __name__ == "__main__":
    main()
