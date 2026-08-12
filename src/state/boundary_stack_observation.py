from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class BoundaryStackObservation:
    """
    Objective stack evidence captured at the boundary ending one betting street.

    This object is evidence only.

    It does not:
    - mutate CanonicalHand
    - update last_confirmed_stack_bb
    - create a CanonicalAction
    - consume an action queue
    - infer CALL / BET / RAISE / FOLD

    Poker semantics belong to a later resolver.
    """

    street: str
    seat: str

    previous_stack_bb: Optional[float]
    observed_stack_bb: Optional[float]

    confidence: float = 0.0
    votes: int = 0
    mode: str = ""

    frame_path: str = ""
    ts: Optional[float] = None

    @property
    def delta_bb(self) -> Optional[float]:
        """
        Positive value means the displayed stack decreased between the
        authoritative previous stack and the boundary observation.
        """
        if (
            self.previous_stack_bb is None
            or self.observed_stack_bb is None
        ):
            return None

        return round(
            float(self.previous_stack_bb)
            - float(self.observed_stack_bb),
            4,
        )

    @property
    def stack_decreased(self) -> bool:
        delta = self.delta_bb
        return delta is not None and delta > 0.0

    @property
    def stack_unchanged(self) -> bool:
        delta = self.delta_bb
        return delta is not None and abs(delta) <= 0.0001

    def to_dict(self) -> dict:
        item = asdict(self)
        item["delta_bb"] = self.delta_bb
        item["stack_decreased"] = self.stack_decreased
        item["stack_unchanged"] = self.stack_unchanged
        return item
