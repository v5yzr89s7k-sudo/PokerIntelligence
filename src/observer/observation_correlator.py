from dataclasses import dataclass, field
from typing import Dict, List

from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
)


@dataclass
class EvidenceGroup:
    seat: str
    observations: List[dict] = field(default_factory=list)
    confidence: float = 0.0

    def add(self, obs):
        self.observations.append(obs.to_dict())

        score = 0.0
        kinds = {o["type"] for o in self.observations}

        if STACK_CHANGED in kinds:
            score += 0.40

        if BET_REGION_OCCUPIED in kinds:
            score += 0.35

        if POT_CHANGED in kinds:
            score += 0.25

        self.confidence = min(score, 1.0)


class ObservationCorrelator:
    def __init__(self):
        self.groups: Dict[str, EvidenceGroup] = {}

    def ingest(self, observations):
        for obs in observations:
            seat = obs.seat or "table"

            group = self.groups.setdefault(
                seat,
                EvidenceGroup(seat=seat),
            )

            group.add(obs)

    def summary(self):
        return {
            seat: {
                "confidence": round(group.confidence, 2),
                "count": len(group.observations),
            }
            for seat, group in self.groups.items()
        }
