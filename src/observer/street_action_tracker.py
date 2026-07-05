from dataclasses import dataclass, field
from typing import Dict, List, Optional
from src.observer.observation_types import Observation, BOARD_CHANGED


@dataclass
class StreetActionTracker:
    current_street: str = "PREFLOP"
    street_open: bool = True
    observations_by_street: Dict[str, List[dict]] = field(default_factory=dict)
    last_observation_type: Optional[str] = None

    def open_street(self, street: str):
        self.current_street = street
        self.street_open = True
        self.observations_by_street.setdefault(street, [])

    def close_street(self):
        self.street_open = False

    def process(self, observation: Observation):
        street = observation.street or self.current_street

        if observation.type == BOARD_CHANGED:
            # A board change objectively ends the previous street and opens the new street.
            # The observation itself belongs to the newly detected street.
            if street and street != self.current_street:
                self.close_street()
                self.open_street(street)
            else:
                self.close_street()

        self.observations_by_street.setdefault(street, [])
        self.observations_by_street[street].append(observation.to_dict())
        self.last_observation_type = observation.type

    def process_many(self, observations):
        for obs in observations:
            self.process(obs)

    def summary(self):
        return {
            "current_street": self.current_street,
            "street_open": self.street_open,
            "last_observation_type": self.last_observation_type,
            "observation_counts": {
                street: len(items)
                for street, items in self.observations_by_street.items()
            },
        }
