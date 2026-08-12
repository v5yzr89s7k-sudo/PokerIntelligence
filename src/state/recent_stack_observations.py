from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TrustedStackObservation:
    """
    Historical perception evidence for one stack read.

    This is NOT canonical stack state.

    It must never:
    - mutate CanonicalHand
    - replace last_confirmed_stack_bb
    - create a CanonicalAction
    - consume betting state
    """

    seat: str
    stack_bb: float
    confidence: float
    votes: int
    mode: str
    frame_path: str = ""
    ts: Optional[float] = None

    def to_dict(self):
        return asdict(self)


class RecentStackObservations:
    """
    Small bounded per-seat history of trusted visual stack observations.

    Purpose:
        preserve already-observed visual evidence long enough for a later
        street-boundary resolver to use it.

    This store owns no poker semantics and no authoritative stack state.
    """

    def __init__(
        self,
        max_per_seat: int = 8,
        minimum_confidence: float = 0.95,
        minimum_votes: int = 2,
    ):
        self.max_per_seat = int(max_per_seat)
        self.minimum_confidence = float(minimum_confidence)
        self.minimum_votes = int(minimum_votes)
        self._by_seat: Dict[str, List[TrustedStackObservation]] = {}

    def clear(self):
        self._by_seat.clear()

    def add(
        self,
        *,
        seat,
        stack_bb,
        confidence,
        votes,
        mode,
        frame_path="",
        ts=None,
    ) -> bool:
        if not seat:
            return False

        if stack_bb is None:
            return False

        try:
            stack_bb = float(stack_bb)
            confidence = float(confidence or 0.0)
            votes = int(votes or 0)
        except (TypeError, ValueError):
            return False

        if stack_bb < 0.0:
            return False

        if confidence < self.minimum_confidence:
            return False

        if votes < self.minimum_votes:
            return False

        observation = TrustedStackObservation(
            seat=str(seat),
            stack_bb=stack_bb,
            confidence=confidence,
            votes=votes,
            mode=str(mode or ""),
            frame_path=str(frame_path or ""),
            ts=float(ts) if ts is not None else None,
        )

        history = self._by_seat.setdefault(str(seat), [])

        # Identical evidence from the same source frame is duplicate evidence,
        # not another independent observation.
        if history:
            last = history[-1]
            if (
                last.frame_path
                and observation.frame_path
                and last.frame_path == observation.frame_path
                and abs(last.stack_bb - observation.stack_bb) <= 0.0001
            ):
                return False

        history.append(observation)

        if len(history) > self.max_per_seat:
            del history[:-self.max_per_seat]

        return True

    def history(self, seat):
        return list(self._by_seat.get(str(seat), []))

    def latest(self, seat):
        history = self._by_seat.get(str(seat), [])
        return history[-1] if history else None

    def strongest_recent(
        self,
        seat,
        *,
        not_after_ts=None,
        max_age_seconds=None,
    ):
        candidates = self.history(seat)

        if not_after_ts is not None:
            boundary_ts = float(not_after_ts)
            candidates = [
                item
                for item in candidates
                if item.ts is None or item.ts <= boundary_ts
            ]

            if max_age_seconds is not None:
                minimum_ts = boundary_ts - float(max_age_seconds)
                candidates = [
                    item
                    for item in candidates
                    if item.ts is None or item.ts >= minimum_ts
                ]

        if not candidates:
            return None

        # Trust first, recency second. All entries already satisfy the
        # minimum trust contract.
        return max(
            candidates,
            key=lambda item: (
                item.votes,
                item.confidence,
                item.ts if item.ts is not None else float("-inf"),
            ),
        )

    def to_dict(self):
        return {
            seat: [
                item.to_dict()
                for item in history
            ]
            for seat, history in self._by_seat.items()
        }
