from dataclasses import dataclass
from unittest.mock import patch

from src.observer.action_episode_manager import ActionEpisodeManager
from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
)


@dataclass
class FakeObservation:
    type: str
    ts: float
    seat: str = "hero"
    street: str = "FLOP"
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

with patch("src.observer.action_episode_manager.time.time", return_value=10.00):
    manager.ingest([
        FakeObservation(STACK_CHANGED, 10.00),
        FakeObservation(BET_REGION_OCCUPIED, 10.00),
    ])

with patch("src.observer.action_episode_manager.time.time", return_value=10.20):
    manager.ingest([
        FakeObservation(BET_REGION_CLEARED, 10.20),
    ])

assert len(manager.active_by_seat) == 1
assert len(manager.closed) == 0

# Late pot/stack evidence must remain in the same episode.
with patch("src.observer.action_episode_manager.time.time", return_value=10.55):
    manager.ingest([
        FakeObservation(POT_CHANGED, 10.55, seat=None),
        FakeObservation(STACK_CHANGED, 10.55),
    ])

assert len(manager.active_by_seat) == 1
assert len(manager.closed) == 0

with patch("src.observer.action_episode_manager.time.time", return_value=11.05):
    manager.close_idle()

assert len(manager.active_by_seat) == 0
assert len(manager.closed) == 1

episode = manager.closed[0].to_dict()
kinds = episode["observation_types"]

# The first stack change occurred before direct chip evidence and must
# be ignored. Only the later stack change strengthens the open episode.
assert kinds.count(STACK_CHANGED) == 1
assert BET_REGION_OCCUPIED in kinds
assert BET_REGION_CLEARED in kinds
assert POT_CHANGED in kinds
assert episode["close_reason"] == "bet_region_settled"

print(episode)
print()
print("ActionEpisode stabilization smoke test passed.")
