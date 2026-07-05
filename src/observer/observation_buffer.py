from collections import deque
from typing import Iterable, List
from src.observer.observation_types import Observation


class ObservationBuffer:
    def __init__(self, maxlen=500):
        self.items = deque(maxlen=maxlen)

    def append(self, observation: Observation):
        self.items.append(observation)

    def extend(self, observations: Iterable[Observation]):
        for obs in observations:
            self.append(obs)

    def recent(self, n=50) -> List[Observation]:
        return list(self.items)[-n:]

    def by_street(self, street: str) -> List[Observation]:
        return [obs for obs in self.items if obs.street == street]

    def clear(self):
        self.items.clear()

    def to_list(self):
        return [obs.to_dict() for obs in self.items]
