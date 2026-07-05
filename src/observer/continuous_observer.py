from typing import List
from src.observer.observation_buffer import ObservationBuffer
from src.observer.observation_types import (
    Observation,
    BOARD_CHANGED,
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    HERO_CARDS_VISIBLE,
    ACTION_BUTTONS_VISIBLE,
    DEALER_CHANGED,
    POT_CHANGED,
)
from src.observer.street_action_tracker import StreetActionTracker


def observations_from_changes(changes, street="unknown") -> List[Observation]:
    observations = []

    if getattr(changes, "board_changed", False):
        observations.append(Observation(
            type=BOARD_CHANGED,
            street=street,
            payload={"board_count": getattr(changes, "board_count", 0)},
        ))

    for seat in getattr(changes, "stack_changed_seats", []) or []:
        details = getattr(changes, "stack_change_details", {}) or {}
        observations.append(Observation(
            type=STACK_CHANGED,
            street=street,
            seat=seat,
            payload=details.get(seat) or {},
        ))

    for seat in getattr(changes, "occupied_bet_regions", []) or []:
        details = getattr(changes, "bet_region_occupancy", {}) or {}
        observations.append(Observation(
            type=BET_REGION_OCCUPIED,
            street=street,
            seat=seat,
            payload=details.get(seat) or {},
        ))

    if getattr(changes, "hero_cards_visible", False):
        observations.append(Observation(type=HERO_CARDS_VISIBLE, street=street, seat="hero"))

    if getattr(changes, "action_buttons_visible", False):
        observations.append(Observation(type=ACTION_BUTTONS_VISIBLE, street=street, seat="hero"))

    if getattr(changes, "dealer_changed", False):
        observations.append(Observation(type=DEALER_CHANGED, street=street))

    if getattr(changes, "pot_changed", False):
        observations.append(Observation(type=POT_CHANGED, street=street))

    return observations


class ContinuousObserver:
    def __init__(self, max_buffer=500):
        self.buffer = ObservationBuffer(maxlen=max_buffer)
        self.street_tracker = StreetActionTracker()

    def ingest_changes(self, changes, street="unknown"):
        observations = observations_from_changes(changes, street=street)
        self.buffer.extend(observations)
        self.street_tracker.process_many(observations)
        return observations

    def summary(self):
        return {
            "buffer_size": len(self.buffer.items),
            "street_tracker": self.street_tracker.summary(),
        }
