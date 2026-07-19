import time

from src.observer.action_episode_manager import ActionEpisodeManager
from src.observer.observation_types import Observation
from src.observer.observation_types import (
    BET_REGION_OCCUPIED,
    STACK_CHANGED,
)


manager = ActionEpisodeManager(
    idle_timeout=0.01,
    settle_timeout=0.01,
    late_stack_attach_seconds=2.75,
)

started = time.time()

manager.ingest([
    Observation(
        type=BET_REGION_OCCUPIED,
        ts=started,
        street="PREFLOP",
        seat="seat_mid_right",
        confidence=0.35,
        payload={},
    )
])

manager.close_idle(started + 0.02)

assert len(manager.closed) == 1
assert [
    item.get("type")
    for item in manager.closed[0].observations
] == [
    BET_REGION_OCCUPIED
]

manager.ingest([
    Observation(
        type=STACK_CHANGED,
        ts=started + 0.50,
        street="PREFLOP",
        seat="seat_mid_right",
        confidence=0.98,
        payload={
            "previous_stack_bb": 100.0,
            "current_stack_bb": 97.5,
            "delta_bb": 2.5,
        },
    )
])

episode = manager.closed[0]
kinds = {
    item.get("type")
    for item in episode.observations
}

assert STACK_CHANGED in kinds
assert episode.confidence >= 0.75
assert not manager.pending_stack_by_seat

print("Late stack episode attachment regression test passed.")
