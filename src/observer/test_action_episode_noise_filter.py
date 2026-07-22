from dataclasses import dataclass
from unittest.mock import patch

from src.observer.action_episode_manager import ActionEpisodeManager
from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
)


@dataclass
class FakeObservation:
    type: str
    ts: float
    seat: str = "seat_mid_left"
    street: str = "PREFLOP"
    payload: dict = None

    def to_dict(self):
        return {
            "type": self.type,
            "ts": self.ts,
            "seat": self.seat,
            "street": self.street,
            "payload": self.payload or {},
        }


manager = ActionEpisodeManager(
    idle_timeout=1.25,
    settle_timeout=0.80,
)

# Stack animation noise must not open an episode.
with patch("src.observer.action_episode_manager.time.time", return_value=1.0):
    manager.ingest([
        FakeObservation(STACK_CHANGED, 1.0),
        FakeObservation(STACK_CHANGED, 1.0, seat="hero"),
    ])

assert manager.active_by_seat == {}
assert manager.closed == []

# Direct bet evidence opens an episode.
with patch("src.observer.action_episode_manager.time.time", return_value=2.0):
    manager.ingest([
        FakeObservation(BET_REGION_OCCUPIED, 2.0),
    ])

assert "seat_mid_left" in manager.active_by_seat

# A later stack change strengthens that same episode.
with patch("src.observer.action_episode_manager.time.time", return_value=2.2):
    manager.ingest([
        FakeObservation(STACK_CHANGED, 2.2),
        FakeObservation(BET_REGION_CLEARED, 2.2),
    ])

episode = manager.active_by_seat["seat_mid_left"]
kinds = [item["type"] for item in episode.observations]

assert len(kinds) == 3
assert set(kinds) == {
    BET_REGION_OCCUPIED,
    STACK_CHANGED,
    BET_REGION_CLEARED,
}

with patch("src.observer.action_episode_manager.time.time", return_value=3.1):
    manager.close_idle()

assert len(manager.closed) == 1
assert manager.closed[0].close_reason == "bet_region_settled"

print(manager.closed[0].to_dict())
print()
print("ActionEpisode noise-filter smoke test passed.")
