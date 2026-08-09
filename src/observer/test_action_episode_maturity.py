from src.observer.action_episode_manager import ActionEpisode
from src.observer.observation_types import (
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
    STACK_CHANGED,
)


class FakeObservation:
    def __init__(
        self,
        observation_type,
        ts,
        seat="seat_mid_left",
        street="PREFLOP",
        payload=None,
    ):
        self.type = observation_type
        self.ts = ts
        self.seat = seat
        self.street = street
        self.payload = payload or {}

    def to_dict(self):
        return {
            "type": self.type,
            "ts": self.ts,
            "seat": self.seat,
            "street": self.street,
            "payload": dict(self.payload),
        }


episode = ActionEpisode(
    episode_id=1,
    seat="seat_mid_left",
    street="PREFLOP",
    started_ts=1.0,
    updated_ts=1.0,
)

# Visual seat evidence alone is not quantitatively mature.
episode.add(
    FakeObservation(
        BET_REGION_OCCUPIED,
        1.0,
    )
)

assert episode.evidence_mature is False
assert (
    episode.maturity_reason
    == "no_quantitative_stack_commitment"
)

# A table-level pot transition still does not identify which seat committed.
episode.add(
    FakeObservation(
        POT_CHANGED,
        1.1,
        seat=None,
    )
)

assert episode.evidence_mature is False
assert (
    episode.maturity_reason
    == "no_quantitative_stack_commitment"
)

# Visual settlement does not change maturity.
episode.add(
    FakeObservation(
        BET_REGION_CLEARED,
        1.2,
    )
)

assert episode.evidence_mature is False

# Quantitative stack evidence matures the candidate.
episode.add(
    FakeObservation(
        STACK_CHANGED,
        1.3,
        payload={
            "previous_stack_bb": 19.82,
            "current_stack_bb": 12.82,
            "delta_bb": 7.0,
        },
    )
)

assert episode.evidence_mature is True
assert (
    episode.maturity_reason
    == "quantitative_stack_commitment"
)

serialized = episode.to_dict()

assert serialized["evidence_mature"] is True
assert (
    serialized["maturity_reason"]
    == "quantitative_stack_commitment"
)

print("ActionEpisode evidence maturity regression passed.")
