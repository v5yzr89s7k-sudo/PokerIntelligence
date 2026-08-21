import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="actor-observed-test",
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


def make_state():
    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["hand_token"] = "actor-observed-token"
    state["canonical_snapshot_ready"] = True
    return state


def reset_tracker():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def test_later_actor_resolves_prior_fold_only():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)
    state = make_state()

    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": "actor-observed-token",
            "seat": "seat_upper_right",
            "street": "PREFLOP",
            "source": "bet_region_appeared",
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    assert hand.players["seat_top"].folded

    assert any(
        action.seat == "seat_top"
        and action.action == "FOLD"
        for action in hand.actions
    )

    assert not any(
        action.seat == "seat_upper_right"
        and action.action in {
            "FOLD",
            "CALL",
            "BET",
            "RAISE",
        }
        for action in hand.actions
    )

    assert hand.players_to_act == [
        "seat_upper_right",
        "hero",
    ]


def test_same_frame_blocker_prevents_false_fold():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)
    state = make_state()

    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": "actor-observed-token",
            "seat": "seat_upper_right",
            "street": "PREFLOP",
            "source": "bet_region_appeared",
            "blocked_seats": ["seat_top"],
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    assert not hand.players["seat_top"].folded

    assert not any(
        action.seat == "seat_top"
        and action.action == "FOLD"
        for action in hand.actions
    )

    assert hand.players_to_act == [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]


def test_unresolved_prior_commitment_blocks_gap():
    reset_tracker()

    hand = make_hand()
    sm.canonical_save(hand)
    state = make_state()

    state = sm.handle_stack_candidate_opened(
        state,
        {
            "type": "stack_candidate_opened",
            "hand_token": "actor-observed-token",
            "seat": "seat_top",
            "street": "PREFLOP",
            "sources": ["stack_motion"],
            "ts": 1.5,
        },
    )

    state = sm.handle_actor_observed(
        state,
        {
            "type": "actor_observed",
            "hand_token": "actor-observed-token",
            "seat": "seat_upper_right",
            "street": "PREFLOP",
            "source": "bet_region_appeared",
            "ts": 2.0,
        },
    )

    hand = sm.canonical_load()

    assert not hand.players["seat_top"].folded

    assert not any(
        action.seat == "seat_top"
        and action.action == "FOLD"
        for action in hand.actions
    )

    assert hand.players_to_act == [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]


if __name__ == "__main__":
    test_later_actor_resolves_prior_fold_only()
    test_same_frame_blocker_prevents_false_fold()
    test_unresolved_prior_commitment_blocks_gap()

    print(
        "PASS actor_observed state-machine contract: "
        "later physical actor resolves only safe chronological predecessors"
    )
