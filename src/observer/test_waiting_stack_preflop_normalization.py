from unittest.mock import patch

from src.observer.action_episode_manager import ActionEpisodeManager
from src.observer.action_inference_engine import (
    ActionInferenceEngine,
    BET_OR_RAISE,
)
from src.observer.observation_types import (
    Observation,
    BET_REGION_OCCUPIED,
    STACK_CHANGED,
)


manager = ActionEpisodeManager(
    idle_timeout=0.01,
    settle_timeout=0.01,
    pending_stack_ttl=1.0,
)

with patch(
    "src.observer.action_episode_manager.time.time",
    return_value=10.0,
):
    manager.ingest([
        Observation(
            type=STACK_CHANGED,
            ts=10.0,
            street="WAITING",
            seat="seat_lower_left",
            confidence=0.98,
            payload={
                "origin_street": "WAITING",
                "previous_stack_bb": 70.44,
                "current_stack_bb": 64.44,
                "delta_bb": 6.0,
            },
        )
    ])

assert manager.pending_stack_by_seat["seat_lower_left"].street == "WAITING"

context = {
    "phase": "PREFLOP",
    "hand_started_at": 9.0,
    "hero_position": "CO",
    "positions": {
        "seat_lower_left": "BTN",
        "hero": "CO",
    },
    "prior_voluntary_commitment_seats": [],
    "prior_occupied_bet_regions": [],
}

manager.set_table_context(context)
manager.backfill_table_context(context)

pending = manager.pending_stack_by_seat["seat_lower_left"]

assert pending.street == "PREFLOP"
assert pending.payload["origin_street"] == "WAITING"

with patch(
    "src.observer.action_episode_manager.time.time",
    return_value=10.5,
):
    manager.ingest([
        Observation(
            type=BET_REGION_OCCUPIED,
            ts=10.5,
            street="PREFLOP",
            seat="seat_lower_left",
            confidence=0.35,
            payload={},
        )
    ])

episode = manager.active_by_seat["seat_lower_left"]
kinds = [item["type"] for item in episode.observations]

assert BET_REGION_OCCUPIED in kinds
assert STACK_CHANGED in kinds
assert not manager.pending_stack_by_seat

manager.close_idle(10.6)

assert len(manager.closed) == 1

engine = ActionInferenceEngine()
actions = engine.ingest_closed(manager.closed)

assert len(actions) == 1
assert actions[0].action == BET_OR_RAISE
assert actions[0].street == "PREFLOP"

print("WAITING stack preflop normalization regression passed.")
