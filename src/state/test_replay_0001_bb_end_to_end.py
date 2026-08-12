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
        hand_id="replay-0001-bb-e2e",
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


def infer_real_bb_episode():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    manager.set_table_context({
        "phase": "PREFLOP",
        "positions": POSITIONS,
        "hero_position": "BTN",
        "prior_voluntary_commitment_seats": [
            "hero",
        ],
        "prior_occupied_bet_regions": [
            "seat_mid_left",
        ],
    })

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.0,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_OCCUPIED,
                ts=10.0,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={"occupied": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.6,
    ):
        manager.ingest([
            Observation(
                type=STACK_CHANGED,
                ts=10.6,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={
                    "previous_stack_bb": 65.6,
                    "current_stack_bb": 56.6,
                    "delta_bb": 9.0,
                    "origin_street": "PREFLOP",
                    "stack_read_mode": "psm13_verification",
                },
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=10.8,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_CLEARED,
                ts=10.8,
                street="PREFLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={"cleared": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=11.7,
    ):
        manager.close_idle()

    assert len(manager.closed) == 1

    episode = manager.closed[0]

    inferred = ActionInferenceEngine().infer_episode(
        episode
    )

    assert inferred.action == CALL_OR_RAISE, inferred
    assert (
        inferred.measurements["stack_change"]["delta_bb"]
        == 9.0
    )

    return inferred


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # First observed voluntary action: Hero opens to 3.5.
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
        "ts": 9.0,
    })

    assert hero_open is not None
    assert hero_open.action == "RAISE"
    assert hero_open.raise_to_bb == 3.5

    # This is the actual semantic output of the Replay 0001 BB episode.
    inferred_bb = infer_real_bb_episode()

    print("===== INFERRED BB =====")
    print(inferred_bb.to_dict())

    bb_action = tracker.ingest(inferred_bb)

    print()
    print("===== CANONICAL BB =====")
    print(bb_action)

    assert bb_action is not None
    assert bb_action.seat == "seat_mid_left"
    assert bb_action.position == "BB"
    assert bb_action.action == "RAISE"
    assert bb_action.raise_to_bb == 10.0
    assert bb_action.amount_bb is None

    # SB must have been resolved as the skipped fold before BB acts.
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
        ("seat_upper_left", "FOLD", None),
        ("seat_top", "FOLD", None),
        ("seat_mid_right", "FOLD", None),
        ("seat_lower_right", "FOLD", None),
        ("hero", "RAISE", 3.5),
        ("seat_lower_left", "FOLD", None),
        ("seat_mid_left", "RAISE", 10.0),
    ]

    actual = [
        (
            action.seat,
            action.action,
            action.raise_to_bb,
        )
        for action in voluntary
    ]

    print()
    print("===== ACTUAL PREFIX =====")
    for item in actual:
        print(item)

    assert actual == expected, (actual, expected)

    print()
    print(
        "PASS Replay 0001 BB end-to-end: "
        "mature episode -> CALL_OR_RAISE -> "
        "BB raises to 10 BB"
    )


if __name__ == "__main__":
    main()
