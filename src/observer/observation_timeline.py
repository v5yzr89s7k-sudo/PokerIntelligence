import json
import time
from pathlib import Path
from typing import Iterable
from src.observer.observation_types import Observation


class ObservationTimeline:
    def __init__(self):
        self.started_ts = time.time()
        self.items = []
        self.by_street = {}

    def add_many(self, observations: Iterable[Observation]):
        for obs in observations:
            self.add(obs)

    def add(self, observation: Observation):
        item = observation.to_dict()
        item["elapsed"] = round(float(item["ts"]) - self.started_ts, 3)

        street = item.get("street") or "unknown"
        self.items.append(item)
        self.by_street.setdefault(street, []).append(item)

    def to_dict(self):
        return {
            "started_ts": self.started_ts,
            "updated_ts": time.time(),
            "count": len(self.items),
            "by_street_counts": {
                street: len(items)
                for street, items in self.by_street.items()
            },
            "items": self.items,
        }

    def write_json(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
