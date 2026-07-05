from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time

from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
)


@dataclass
class ActionEpisode:
    episode_id: int
    seat: str
    street: str
    started_ts: float
    updated_ts: float
    ended_ts: Optional[float] = None
    observations: List[dict] = field(default_factory=list)
    confidence: float = 0.0
    closed: bool = False
    close_reason: str = ""

    def add(self, observation):
        item = observation.to_dict()
        self.observations.append(item)
        self.updated_ts = item["ts"]
        self.recalculate_confidence()

    def recalculate_confidence(self):
        kinds = {o.get("type") for o in self.observations}

        score = 0.0
        if STACK_CHANGED in kinds:
            score += 0.40
        if BET_REGION_OCCUPIED in kinds:
            score += 0.35
        if POT_CHANGED in kinds:
            score += 0.20
        if BET_REGION_CLEARED in kinds:
            score += 0.05

        self.confidence = min(score, 1.0)

    def close(self, reason=""):
        if not self.closed:
            self.closed = True
            self.ended_ts = time.time()
            self.close_reason = reason

    def to_dict(self):
        return {
            "episode_id": self.episode_id,
            "seat": self.seat,
            "street": self.street,
            "started_ts": self.started_ts,
            "updated_ts": self.updated_ts,
            "ended_ts": self.ended_ts,
            "duration": round((self.ended_ts or self.updated_ts) - self.started_ts, 3),
            "observation_count": len(self.observations),
            "observation_types": [o.get("type") for o in self.observations],
            "confidence": round(self.confidence, 2),
            "closed": self.closed,
            "close_reason": self.close_reason,
            "observations": self.observations,
        }


class ActionEpisodeManager:
    def __init__(self, idle_timeout=1.25):
        self.idle_timeout = idle_timeout
        self.next_episode_id = 1
        self.active_by_seat: Dict[str, ActionEpisode] = {}
        self.closed: List[ActionEpisode] = []

    def _relevant(self, observation):
        return observation.type in {
            STACK_CHANGED,
            BET_REGION_OCCUPIED,
            BET_REGION_CLEARED,
            POT_CHANGED,
        }

    def _episode_seat(self, observation):
        return observation.seat or "table"

    def _open_episode(self, seat, street, ts):
        ep = ActionEpisode(
            episode_id=self.next_episode_id,
            seat=seat,
            street=street,
            started_ts=ts,
            updated_ts=ts,
        )
        self.next_episode_id += 1
        self.active_by_seat[seat] = ep
        return ep

    def ingest(self, observations):
        now = time.time()

        for obs in observations:
            if not self._relevant(obs):
                continue

            seat = self._episode_seat(obs)
            street = obs.street or "unknown"

            # Pot changes are table-level, but they should only strengthen episodes
            # that already have direct chip-commit evidence. Do not spray pot_changed
            # across every stack-change episode.
            if obs.type == POT_CHANGED and seat == "table":
                matched = False
                for ep in list(self.active_by_seat.values()):
                    kinds = {o.get("type") for o in ep.observations}
                    if (
                        not ep.closed
                        and ep.street == street
                        and BET_REGION_OCCUPIED in kinds
                    ):
                        ep.add(obs)
                        matched = True
                if matched:
                    continue
                continue

            # A clear without an active episode is usually stale animation cleanup.
            # Do not create a new episode from a lone cleared signal.
            if obs.type == BET_REGION_CLEARED and seat not in self.active_by_seat:
                continue

            ep = self.active_by_seat.get(seat)
            if ep is None or ep.closed or ep.street != street:
                ep = self._open_episode(seat, street, obs.ts)

            ep.add(obs)

            if obs.type == BET_REGION_CLEARED:
                self._close_episode(seat, "bet_region_cleared")

        self.close_idle(now)

    def _close_episode(self, seat, reason):
        ep = self.active_by_seat.get(seat)
        if not ep or ep.closed:
            return

        ep.close(reason)
        self.closed.append(ep)
        self.active_by_seat.pop(seat, None)

    def close_idle(self, now=None):
        now = now or time.time()
        for seat, ep in list(self.active_by_seat.items()):
            if now - ep.updated_ts >= self.idle_timeout:
                self._close_episode(seat, "idle_timeout")

    def to_dict(self):
        return {
            "active": [ep.to_dict() for ep in self.active_by_seat.values()],
            "closed": [ep.to_dict() for ep in self.closed],
            "active_count": len(self.active_by_seat),
            "closed_count": len(self.closed),
        }

    def summary(self):
        data = self.to_dict()
        return {
            "active_count": data["active_count"],
            "closed_count": data["closed_count"],
            "active": [
                {
                    "episode_id": ep["episode_id"],
                    "seat": ep["seat"],
                    "street": ep["street"],
                    "confidence": ep["confidence"],
                    "observation_types": ep["observation_types"],
                }
                for ep in data["active"]
            ],
            "closed_tail": [
                {
                    "episode_id": ep["episode_id"],
                    "seat": ep["seat"],
                    "street": ep["street"],
                    "confidence": ep["confidence"],
                    "close_reason": ep["close_reason"],
                    "observation_types": ep["observation_types"],
                }
                for ep in data["closed"][-10:]
            ],
        }
