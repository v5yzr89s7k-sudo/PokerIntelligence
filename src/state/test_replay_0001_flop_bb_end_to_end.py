from unittest.mock import patch

from src.observer.action_episode_manager import (
    ActionEpisodeManager,
)
from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    BET_OR_RAISE,
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


def make_flop_hand():
    players = [
        {
            "seat": seat,
            "name": seat,
            "stack_bb": 100,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="replay-0001-flop-bb-e2e",
        players=players,
        hero_cards=["6c", "8d"],
        hero_position="BTN",
        positions=POSITIONS,
    )

    hand.dealt_in_seats = list(POSITIONS)

    # Only BB and BTN reached the flop.
    for seat in (
        "seat_upper_left",
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "seat_lower_left",
    ):
        hand.players[seat].folded = True
        hand.players[seat].active = False

    hand.set_board(
        ["Ad", "3d", "3c"],
        ts=20.0,
    )

    hand.players_to_act = [
        "seat_mid_left",
        "hero",
    ]

    hand.current_bet_bb = 0.0

    return hand


def infer_bb_flop_bet():
    manager = ActionEpisodeManager(
        idle_timeout=1.25,
        settle_timeout=0.80,
    )

    manager.set_table_context({
        "phase": "FLOP",
        "positions": POSITIONS,
        "hero_position": "BTN",

        # New street: nobody has made a voluntary flop commitment yet.
        "prior_voluntary_commitment_seats": [],

        "prior_occupied_bet_regions": [],
    })

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.0,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_OCCUPIED,
                ts=30.0,
                street="FLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={"occupied": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.6,
    ):
        manager.ingest([
            Observation(
                type=STACK_CHANGED,
                ts=30.6,
                street="FLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={
                    "previous_stack_bb": 56.6,
                    "current_stack_bb": 51.6,
                    "delta_bb": 5.0,
                    "origin_street": "FLOP",
                    "stack_read_mode": "continuity",
                },
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=30.8,
    ):
        manager.ingest([
            Observation(
                type=BET_REGION_CLEARED,
                ts=30.8,
                street="FLOP",
                seat="seat_mid_left",
                confidence=0.95,
                payload={"cleared": True},
            ),
        ])

    with patch(
        "src.observer.action_episode_manager.time.time",
        return_value=31.7,
    ):
        manager.close_idle()

    assert len(manager.closed) == 1, manager.to_dict()

    episode = manager.closed[0]

    inferred = ActionInferenceEngine().infer_episode(
        episode
    )

    print("===== INFERRED FLOP BB =====")
    print(inferred.to_dict())

    assert inferred.action == BET_OR_RAISE, inferred
    assert inferred.seat == "seat_mid_left"
    assert inferred.street == "FLOP"

    stack = (
        inferred.measurements.get("stack_change")
        or {}
    )

    assert stack.get("previous_stack_bb") == 56.6
    assert stack.get("current_stack_bb") == 51.6
    assert stack.get("delta_bb") == 5.0

    return inferred


def main():
    hand = make_flop_hand()
    tracker = BettingRoundTracker(hand)

    inferred = infer_bb_flop_bet()

    action = tracker.ingest(inferred)

    print()
    print("===== CANONICAL FLOP BB =====")
    print(action)

    assert action is not None
    assert action.seat == "seat_mid_left"
    assert action.position == "BB"
    assert action.street == "FLOP"
    assert action.action == "BET"
    assert action.amount_bb == 5.0
    assert action.raise_to_bb is None

    flop_actions = [
        item
        for item in hand.actions
        if item.street == "FLOP"
    ]

    actual = [
        (
            item.position,
            item.action,
            item.amount_bb,
            item.raise_to_bb,
        )
        for item in flop_actions
    ]

    print()
    print("===== FLOP ACTIONS =====")
    for item in actual:
        print(item)

    assert actual == [
        ("BB", "BET", 5.0, None),
    ], actual

    assert hand.current_bet_bb == 5.0

    print()
    print(
        "PASS Replay 0001 flop BB end-to-end: "
        "real 5 BB commitment -> BET_OR_RAISE -> "
        "BB bets 5 BB"
    )


if __name__ == "__main__":
    main()
