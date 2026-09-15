"""
Physical actor-completion arbitration.

Contract:

1. Raw bet-region evidence alone is only a visual hypothesis.
   It cannot veto calibrated card disappearance for the current actor.

2. A quantitatively validated stack transition awaiting semantic action
   is independent commitment evidence and must still veto fold resolution.

3. A later-seat card disappearance may never jump unresolved predecessors.
"""

from unittest.mock import patch

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


TOKEN = "physical-completion-arbitration"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="physical-completion-arbitration-hand",
        players=[
            {
                "seat": "seat_top",
                "name": "CO",
                "stack_bb": 40.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
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


def make_state():
    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["physical_street"] = "PREFLOP"
    state["canonical_snapshot_ready"] = True
    state["hand_token"] = TOKEN
    return state


def completion(seat="seat_top"):
    return {
        "type": "physical_actor_completed",
        "hand_token": TOKEN,
        "seat": seat,
        "street": "PREFLOP",
        "source": "opponent_card_disappearance",
        "evidence": [
            "opponent_cards_visible_before",
            "opponent_cards_absent_after",
            "calibrated_acr_card_back",
        ],
        "ts": 20.0,
    }


def test_raw_roi_does_not_veto_completion():
    state = make_state()

    state["unresolved_stack_candidates"] = {
        "PREFLOP:seat_top": {
            "seat": "seat_top",
            "street": "PREFLOP",
            "sources": [
                "bet_region_appeared",
            ],
            "ts": 10.0,
        }
    }

    blocked = sm.physical_completion_stack_blocked(
        state,
        "PREFLOP",
        "seat_top",
    )

    print(
        "raw_roi_blocked=",
        blocked,
    )

    assert blocked is False, (
        "RED: raw uncorroborated bet-region appearance "
        "still vetoes calibrated card disappearance"
    )


def test_validated_stack_transition_still_vetoes():
    state = make_state()

    state["unresolved_stack_candidates"] = {
        "PREFLOP:seat_top": {
            "seat": "seat_top",
            "street": "PREFLOP",
            "sources": [
                "stack_motion",
                "bet_region_appeared",
            ],
            "awaiting_action": True,
            "resolved_reason": "validated_stack_transition",
            "resolved_ts": 15.0,
            "ts": 10.0,
        }
    }

    blocked = sm.physical_completion_stack_blocked(
        state,
        "PREFLOP",
        "seat_top",
    )

    print(
        "validated_transition_blocked=",
        blocked,
    )

    assert blocked is True, (
        "RED: validated quantitative commitment lost "
        "authority against card disappearance"
    )


def test_end_to_end_raw_roi_then_fold():
    sm.reset_tracker()

    hand = make_hand()
    tracker = BettingRoundTracker(hand)
    state = make_state()

    state["unresolved_stack_candidates"] = {
        "PREFLOP:seat_top": {
            "seat": "seat_top",
            "street": "PREFLOP",
            "sources": [
                "bet_region_appeared",
            ],
            "ts": 10.0,
        }
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
        "write_betting_round_status",
    ):
        state = sm.handle_physical_actor_completed(
            state,
            completion(),
        )

    actions = [
        (
            action.seat,
            action.action,
        )
        for action in hand.actions
    ]

    print(
        "raw_roi_then_completion_actions=",
        actions,
    )

    assert (
        "seat_top",
        "FOLD",
    ) in actions, (
        "RED: current actor's calibrated card disappearance "
        "cannot resolve FOLD after false raw ROI hypothesis"
    )


def test_later_seat_still_cannot_jump_head():
    sm.reset_tracker()

    hand = make_hand()
    tracker = BettingRoundTracker(hand)
    state = make_state()

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
    ):
        state = sm.handle_physical_actor_completed(
            state,
            completion(seat="hero"),
        )

    assert hand.actions == [], (
        "RED: later-seat completion fabricated chronology"
    )

    assert hand.players_to_act == [
        "seat_top",
        "hero",
    ]

    pending = list(
        state.get(
            "pending_physical_actor_completions"
        )
        or []
    )

    assert pending
    assert pending[0]["seat"] == "hero"

    print(
        "PASS: later-seat completion remains preserved "
        "behind unresolved predecessor"
    )


def main():
    test_raw_roi_does_not_veto_completion()
    test_validated_stack_transition_still_vetoes()
    test_end_to_end_raw_roi_then_fold()
    test_later_seat_still_cannot_jump_head()

    print(
        "PASS physical completion commitment arbitration"
    )


if __name__ == "__main__":
    main()
