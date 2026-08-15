import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="stack-candidate-gap",
        players=[
            {
                "seat": "seat_top",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_upper_right",
                "name": "HJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "seat_top": "UTG",
            "seat_upper_right": "HJ",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0
    hand.players_to_act = [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]

    return hand


def main():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None

    hand = make_hand()
    sm.canonical_save(hand)

    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = "candidate-gap-token"
    state["canonical_snapshot_ready"] = True

    # Candidate evidence arrives before the older action is consumed.
    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": "candidate-gap-token",
            "seat": "seat_top",
            "street": "PREFLOP",
            "sources": ["stack_motion"],
            "ts": 2.0,
        },
    )

    state = sm.handle_inferred_action(
        state,
        {
            "type": "inferred_action",
            "episode_id": 101,
            "seat": "hero",
            "street": "PREFLOP",
            "action": "BET_OR_RAISE",
            "confidence": 0.95,
            "measurements": {
                "stack_change": {
                    "delta_bb": 2.5,
                },
            },
            "evidence": [
                "stack_changed",
                "bet_region_occupied",
            ],
            "ts": 3.0,
        },
    )

    hand = sm.canonical_load()

    assert not hand.players["seat_top"].folded
    assert hand.players["seat_top"].active

    assert not any(
        action.seat == "seat_top"
        and action.action == "FOLD"
        for action in hand.actions
    )

    candidates = (
        state.get("unresolved_stack_candidates")
        or {}
    )

    assert "PREFLOP:seat_top" in candidates

    # Closure clears only the transient evidence.
    state = sm.handle_stack_candidate_closed(
        state,
        {
            "type": "stack_candidate_closed",
            "hand_token": "candidate-gap-token",
            "seat": "seat_top",
            "street": "PREFLOP",
            "reason": "settled",
            "ts": 4.0,
        },
    )

    assert (
        "PREFLOP:seat_top"
        not in (
            state.get("unresolved_stack_candidates")
            or {}
        )
    )

    print(
        "PASS stack-candidate gap state machine: "
        "consumption-time unresolved stack evidence prevents "
        "premature preflop FOLD and closes cleanly"
    )


if __name__ == "__main__":
    main()
