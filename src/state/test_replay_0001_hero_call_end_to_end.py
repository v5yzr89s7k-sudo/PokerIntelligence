from unittest.mock import patch

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    CALL_OR_RAISE,
)
from src.observer.observation_types import (
    Observation,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    STACK_CHANGED,
)
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)


POSITIONS = {
    "seat_upper_left": "UTG",
    "seat_top": "UTG+1",
    "seat_mid_right": "HJ",
    "seat_lower_right": "CO",
    "hero": "BTN",
    "seat_lower_left": "SB",
    "seat_mid_left": "BB",
}


def make_hand():
    players = [
        {
            "seat": seat,
            "name": seat,
            "stack_bb": 100,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="replay-0001-hero-call-e2e",
        players=players,
        hero_cards=["6c", "8d"],
        hero_position="BTN",
        positions=POSITIONS,
    )

    hand.dealt_in_seats = list(POSITIONS)

    for seat in POSITIONS:
        hand.add_action(
            seat=seat,
            action="POST_ANTE",
            amount_bb=0.125,
            confidence=1.0,
            source="replay_0001_seed",
        )

    hand.add_action(
        seat="seat_lower_left",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.add_action(
        seat="seat_mid_left",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.current_bet_bb = 1.0

    hand.players_to_act = [
        "seat_upper_left",
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
    ]

    return hand


def infer_hero_response():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    manager.set_table_context({
        "phase": "PREFLOP",
        "positions": POSITIONS,
        "hero_position": "BTN",

        # Hero has already opened, and BB has now 3-bet.
        "prior_voluntary_commitment_seats": [
            "hero",
            "seat_mid_left",
        ],

        "prior_occupied_bet_regions": [
            "hero",
            "seat_mid_left",
        ],
    })

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.0,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_OCCUPIED,
                ts=20.0,
                street="PREFLOP",
                seat="hero",
                confidence=0.95,
                payload={"occupied": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.6,
    ):
        manager.ingest([
            Observation(
                type=STACK_CHANGED,
                ts=20.6,
                street="PREFLOP",
                seat="hero",
                confidence=0.95,
                payload={
                    "previous_stack_bb": 57.34,
                    "current_stack_bb": 50.84,
                    "delta_bb": 6.5,
                    "origin_street": "PREFLOP",
                    "stack_read_mode": "tiebreak",
                },
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=20.8,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_CLEARED,
                ts=20.8,
                street="PREFLOP",
                seat="hero",
                confidence=0.95,
                payload={"cleared": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=21.7,
    ):
        manager.close_idle()

    assert len(manager.closed) == 1

    episode = manager.closed[0]

    inferred = ActionInferenceEngine().infer_episode(
        episode
    )

    print("===== INFERRED HERO RESPONSE =====")
    print(inferred.to_dict())

    assert inferred.action == CALL_OR_RAISE, inferred
    assert inferred.seat == "hero"
    assert inferred.street == "PREFLOP"
    assert (
        inferred.measurements["stack_change"]["delta_bb"]
        == 6.5
    )

    return inferred


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    hero_open = tracker.ingest({
        "episode_id": 100,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.5,
            },
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 10.0,
    })

    assert hero_open is not None
    assert hero_open.action == "RAISE"
    assert hero_open.raise_to_bb == 3.5

    bb_three_bet = tracker.ingest({
        "episode_id": 101,
        "seat": "seat_mid_left",
        "street": "PREFLOP",
        "action": "CALL_OR_RAISE",
        "confidence": 0.80,
        "measurements": {
            "stack_change": {
                "previous_stack_bb": 65.6,
                "current_stack_bb": 56.6,
                "delta_bb": 9.0,
            },
        },
        "evidence": [
            "bet_region_occupied",
            "stack_changed",
            "bet_region_cleared",
        ],
        "ts": 11.0,
    })

    assert bb_three_bet is not None
    assert bb_three_bet.action == "RAISE"
    assert bb_three_bet.raise_to_bb == 10.0

    inferred_hero = infer_hero_response()

    hero_call = tracker.ingest(
        inferred_hero
    )

    print()
    print("===== CANONICAL HERO RESPONSE =====")
    print(hero_call)

    assert hero_call is not None
    assert hero_call.seat == "hero"
    assert hero_call.position == "BTN"
    assert hero_call.action == "CALL"
    assert hero_call.amount_bb == 6.5
    assert hero_call.raise_to_bb is None

    voluntary = [
        action
        for action in hand.actions
        if action.action not in {
            "POST_ANTE",
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
    ]

    expected = [
        ("seat_upper_left", "FOLD", None, None),
        ("seat_top", "FOLD", None, None),
        ("seat_mid_right", "FOLD", None, None),
        ("seat_lower_right", "FOLD", None, None),
        ("hero", "RAISE", None, 3.5),
        ("seat_lower_left", "FOLD", None, None),
        ("seat_mid_left", "RAISE", None, 10.0),
        ("hero", "CALL", 6.5, None),
    ]

    actual = [
        (
            action.seat,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in voluntary
    ]

    print()
    print("===== ACTUAL PREFLOP =====")
    for item in actual:
        print(item)

    assert actual == expected, (actual, expected)

    print()
    print(
        "PASS Replay 0001 Hero response end-to-end: "
        "real 6.5 BB commitment -> CALL_OR_RAISE -> "
        "BTN calls 6.5 BB"
    )


if __name__ == "__main__":
    main()
