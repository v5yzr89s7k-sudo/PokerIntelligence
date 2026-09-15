"""
September 8 physical-completion / stack-hypothesis lifecycle.

Observed pattern:
    BTN has raw stack-motion evidence.
    No quantitative stack transition is validated.
    BTN's calibrated cards disappear.

Contract:
    - raw stack motion is only a quantitative hypothesis;
    - it must not veto direct current-actor card disappearance;
    - the physical completion resolves FOLD through ActionTimeline;
    - later candidate cleanup cannot erase or duplicate that action;
    - the next current actor can then resolve independently;
    - validated quantitative commitment remains a separate stronger case.
"""

from unittest.mock import patch

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


TOKEN = "physical-supersedes-stack-candidate"


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="physical-supersedes-stack-candidate-hand",
        players=[
            {
                "seat": "seat_upper_right",
                "name": "BTN",
                "stack_bb": 92.0,
                "is_active": True,
            },
            {
                "seat": "seat_lower_right",
                "name": "SB",
                "stack_bb": 13.39,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 12.92,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions={
            "seat_upper_right": "BTN",
            "seat_lower_right": "SB",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    # Model the exact chronology boundary under test:
    # BTN is current actor, then SB, then Hero.
    hand.players_to_act = [
        "seat_upper_right",
        "seat_lower_right",
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


def completion(seat, ts):
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
        "ts": ts,
    }


def action_pairs(hand):
    return [
        (
            action.seat,
            action.action,
        )
        for action in hand.actions
        if action.street == "PREFLOP"
    ]


def main():
    sm.reset_tracker()

    hand = make_hand()
    tracker = BettingRoundTracker(hand)
    state = make_state()

    # --------------------------------------------------------
    # 1. BTN receives only raw stack-motion evidence.
    # --------------------------------------------------------

    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": TOKEN,
            "street": "PREFLOP",
            "seat": "seat_upper_right",
            "sources": [
                "stack_motion",
            ],
            "ts": 10.0,
        },
    )

    print(
        "candidate_state:",
        state.get("unresolved_stack_candidates"),
    )

    assert action_pairs(hand) == [], (
        "raw stack candidate authored a poker action"
    )

    blocked = sm.physical_completion_stack_blocked(
        state,
        "PREFLOP",
        "seat_upper_right",
    )

    print(
        "motion_only_blocked:",
        blocked,
    )

    assert blocked is False, (
        "RED: unresolved raw stack-motion hypothesis "
        "still vetoes direct physical completion"
    )

    # --------------------------------------------------------
    # 2. Same current actor's cards disappear.
    # --------------------------------------------------------

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
            completion(
                "seat_upper_right",
                10.1,
            ),
        )

        print(
            "after_btn_completion:",
            action_pairs(hand),
        )

        print(
            "queue_after_btn:",
            hand.players_to_act,
        )

        assert (
            "seat_upper_right",
            "FOLD",
        ) in action_pairs(hand), (
            "RED: current actor's calibrated card disappearance "
            "did not supersede unresolved stack-motion hypothesis"
        )

        assert hand.players_to_act == [
            "seat_lower_right",
            "hero",
        ], (
            "RED: BTN physical completion did not advance "
            "canonical chronology to SB"
        )

        # ----------------------------------------------------
        # 3. Later candidate cleanup must be harmless.
        # ----------------------------------------------------

        state = sm.handle_stack_candidate_closed(
            state,
            {
                "type": "stack_candidate_closed",
                "hand_token": TOKEN,
                "street": "PREFLOP",
                "seat": "seat_upper_right",
                "sources": [
                    "stack_motion",
                ],
                "reason": "candidate_removed",
                "ts": 11.0,
            },
        )

        print(
            "after_candidate_close:",
            action_pairs(hand),
        )

        assert action_pairs(hand).count(
            (
                "seat_upper_right",
                "FOLD",
            )
        ) == 1, (
            "RED: later stack-candidate cleanup erased "
            "or duplicated the resolved BTN fold"
        )

        # ----------------------------------------------------
        # 4. SB is now the actual current actor.
        # ----------------------------------------------------

        state = sm.handle_physical_actor_completed(
            state,
            completion(
                "seat_lower_right",
                12.0,
            ),
        )

        print(
            "after_sb_completion:",
            action_pairs(hand),
        )

        print(
            "queue_after_sb:",
            hand.players_to_act,
        )

        assert (
            "seat_lower_right",
            "FOLD",
        ) in action_pairs(hand), (
            "RED: once BTN was physically resolved, "
            "SB physical completion could not resolve"
        )

        assert hand.players_to_act == [
            "hero",
        ], (
            "RED: SB completion did not advance "
            "chronology to Hero"
        )

    print(
        "PASS: current-actor card disappearance supersedes "
        "raw stack-motion hypothesis and advances chronology "
        "without fabricating predecessor history"
    )


if __name__ == "__main__":
    main()
