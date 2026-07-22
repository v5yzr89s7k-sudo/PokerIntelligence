from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time

from src.observer.observation_types import (
    STACK_CHANGED,
    BET_REGION_OCCUPIED,
    BET_REGION_CLEARED,
    POT_CHANGED,
)


# Keep late stack attachment and inference delay synchronized.
LATE_STACK_ATTACH_SECONDS = 2.75


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
    pending_close_ts: Optional[float] = None
    table_context: dict = field(default_factory=dict)

    def add(self, observation):
        item = observation.to_dict()
        self.observations.append(item)

        # Late evidence may have been captured before the observation that
        # opened the episode. Never move the episode clock backward.
        self.updated_ts = max(
            float(self.updated_ts),
            float(item["ts"]),
        )

        if item.get("type") == BET_REGION_CLEARED:
            self.pending_close_ts = item["ts"]

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
            "pending_close_ts": self.pending_close_ts,
            "table_context": self.table_context,
            "observations": self.observations,
        }


class ActionEpisodeManager:
    def __init__(
        self,
        idle_timeout=1.25,
        settle_timeout=0.80,
        pending_stack_ttl=0.75,
        late_stack_attach_seconds=LATE_STACK_ATTACH_SECONDS,
    ):
        self.idle_timeout = idle_timeout
        self.settle_timeout = settle_timeout
        self.pending_stack_ttl = float(pending_stack_ttl)
        self.late_stack_attach_seconds = float(
            late_stack_attach_seconds
        )
        self.next_episode_id = 1
        self.active_by_seat: Dict[str, ActionEpisode] = {}
        self.closed: List[ActionEpisode] = []
        self.table_context = {}

        # Stack changes can occur one capture before the bet region appears.
        # Hold unmatched stack evidence briefly instead of discarding it.
        self.pending_stack_by_seat = {}

    def set_table_context(self, context):
        self.table_context = deepcopy(context or {})

    def _normalize_pending_waiting_street(self, context):
        """
        Reclassify pending stack observations captured before the asynchronous
        snapshot initialized the canonical hand.

        The original detector street remains available in
        payload["origin_street"] for diagnostics.
        """
        phase = str((context or {}).get("phase") or "").upper()

        if phase != "PREFLOP":
            return 0

        normalized = 0

        for observation in self.pending_stack_by_seat.values():
            street = str(observation.street or "unknown").upper()

            if street != "WAITING":
                continue

            observation.street = "PREFLOP"
            normalized += 1

            print(
                f"[EPISODE] normalize_pending_stack "
                f"seat={observation.seat} WAITING->PREFLOP",
                flush=True,
            )

        return normalized

    def backfill_table_context(self, context):
        """
        Enrich active and closed episodes from the current hand when the
        asynchronous table snapshot supplies positions after they opened.
        """
        context = deepcopy(context or {})
        hand_started_at = context.get("hand_started_at")
        positions = context.get("positions") or {}

        if hand_started_at is None or not positions:
            return 0

        self._normalize_pending_waiting_street(context)

        updated = 0

        episodes = (
            list(self.active_by_seat.values())
            + list(self.closed)
        )

        for episode in episodes:
            existing = episode.table_context or {}
            episode_hand_started_at = existing.get(
                "hand_started_at"
            )

            if episode_hand_started_at != hand_started_at:
                continue

            existing_positions = existing.get("positions") or {}
            existing_hero_position = (
                existing.get("hero_position")
                or "unknown"
            )

            needs_context = (
                not existing_positions
                or existing_hero_position == "unknown"
            )

            if not needs_context:
                continue

            episode.table_context = deepcopy(context)
            updated += 1

        return updated

    def _expire_pending_stack(self, now):
        expired = []

        for seat, observation in self.pending_stack_by_seat.items():
            if now - observation.ts > self.pending_stack_ttl:
                expired.append(seat)

        for seat in expired:
            self.pending_stack_by_seat.pop(seat, None)

    def _cache_pending_stack(self, observation):
        print(
            f"[EPISODE] cache_pending_stack seat={observation.seat} "
            f"street={observation.street} ts={observation.ts:.3f}",
            flush=True,
        )
        self.pending_stack_by_seat[
            observation.seat or "table"
        ] = observation

    def _attach_late_stack(self, observation):
        seat = observation.seat or "table"
        street = observation.street or "unknown"

        for episode in reversed(self.closed):
            if episode.seat != seat or episode.street != street:
                continue

            if episode.ended_ts is None:
                continue

            age = observation.ts - episode.ended_ts

            if age < 0.0:
                continue

            if age > self.late_stack_attach_seconds:
                break

            kinds = {
                item.get("type")
                for item in episode.observations
            }

            if STACK_CHANGED in kinds:
                return False

            if BET_REGION_OCCUPIED not in kinds:
                continue

            print(
                f"[EPISODE] attach_late_stack "
                f"episode={episode.episode_id} "
                f"seat={seat} street={street}",
                flush=True,
            )
            episode.add(observation)
            return True

        return False

    def _consume_pending_stack(self, seat, street, opened_ts):
        observation = self.pending_stack_by_seat.get(seat)

        if observation is None:
            return None

        age = opened_ts - observation.ts

        valid = (
            0.0 <= age <= self.pending_stack_ttl
            and (observation.street or "unknown") == street
        )

        if not valid:
            if age > self.pending_stack_ttl:
                self.pending_stack_by_seat.pop(
                    seat,
                    None,
                )
            return None

        print(
            f"[EPISODE] consume_pending_stack "
            f"seat={seat} street={street}",
            flush=True,
        )
        self.pending_stack_by_seat.pop(
            seat,
            None,
        )
        return observation

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
            table_context=deepcopy(self.table_context),
        )
        self.next_episode_id += 1
        self.active_by_seat[seat] = ep
        return ep

    def ingest(self, observations):
        now = time.time()
        self._expire_pending_stack(now)

        # Process observations in poker-semantic priority rather than
        # detector arrival order. This allows a stack change detected in
        # the same frame as a newly appearing bet region to attach to the
        # newly opened episode instead of being discarded.
        priority = {
            BET_REGION_OCCUPIED: 0,
            BET_REGION_CLEARED: 1,
            STACK_CHANGED: 2,
            POT_CHANGED: 3,
        }

        observations = sorted(
            observations,
            key=lambda obs: priority.get(obs.type, 99),
        )

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

            # Stack regions are visually noisy. A stack change by itself is not
            # enough evidence to begin a poker-action episode. It may only
            # strengthen an episode already opened by direct chip evidence.
            if obs.type == STACK_CHANGED:
                if ep is None or ep.closed or ep.street != street:
                    if self._attach_late_stack(obs):
                        continue

                    self._cache_pending_stack(obs)
                    continue

                ep.add(obs)
                continue

            # A visible bet/chip region is the primary seat-level episode opener.
            if obs.type == BET_REGION_OCCUPIED:
                opened = False

                if ep is None or ep.closed or ep.street != street:
                    ep = self._open_episode(
                        seat,
                        street,
                        obs.ts,
                    )
                    opened = True

                ep.add(obs)

                if opened:
                    pending_stack = self._consume_pending_stack(
                        seat=seat,
                        street=street,
                        opened_ts=obs.ts,
                    )

                    if pending_stack is not None:
                        ep.add(pending_stack)

                continue

            # A clear without an active episode was already filtered above.
            # When an episode exists, retain the clear and allow the settlement
            # window to collect late stack/pot animation evidence.
            if obs.type == BET_REGION_CLEARED:
                if ep is None or ep.closed or ep.street != street:
                    continue

                ep.add(obs)
                continue

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
            if (
                ep.pending_close_ts is not None
                and now - ep.pending_close_ts >= self.settle_timeout
            ):
                self._close_episode(seat, "bet_region_settled")
                continue

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
                    "table_context": ep.get("table_context", {}),
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
                    "table_context": ep.get("table_context", {}),
                }
                for ep in data["closed"][-10:]
            ],
        }
