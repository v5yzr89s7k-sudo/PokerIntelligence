from dataclasses import dataclass, asdict
from typing import Optional

from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)


@dataclass(frozen=True)
class BoundaryActionResolution:
    """
    Proposed semantic resolution from terminal stack evidence.

    Evidence only: callers decide whether/how to promote this into
    canonical chronology.
    """

    street: str
    seat: str
    action: Optional[str]

    amount_bb: Optional[float] = None
    raise_to_bb: Optional[float] = None

    resolved: bool = False
    reason: str = ""

    confidence: float = 0.0

    def to_dict(self):
        return asdict(self)


def resolve_boundary_action(
    observation: BoundaryStackObservation,
    *,
    owes_action: bool,
    betting_open: bool,
    current_price_bb: float,
    prior_live_commitment_bb: float,
    tolerance: float = 0.05,
) -> BoundaryActionResolution:
    """
    Conservatively resolve one player's terminal street action.

    This function does not mutate betting state or CanonicalHand.

    Supported unique cases:

    1. Facing resolved aggression:
       - unchanged stack -> FOLD
       - stack decrease bringing live commitment exactly to price -> CALL

    2. No open aggression:
       - unchanged stack on a postflop street -> CHECK

    Raises, short all-in calls, and uncertain reads remain unresolved.
    """

    street = str(
        observation.street or "UNKNOWN"
    ).upper()

    seat = observation.seat

    if not owes_action:
        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="player does not owe action on preserved street state",
            confidence=observation.confidence,
        )

    if (
        observation.previous_stack_bb is None
        or observation.observed_stack_bb is None
    ):
        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="boundary stack evidence is incomplete",
            confidence=observation.confidence,
        )

    # Require a genuinely trustworthy stack read before assigning poker
    # semantics. Confidence/vote policy belongs here, not in CanonicalHand.
    if (
        observation.confidence < 0.90
        or observation.votes < 2
    ):
        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="boundary stack evidence is not sufficiently trusted",
            confidence=observation.confidence,
        )

    delta = observation.delta_bb

    if delta is None:
        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="boundary stack delta is unavailable",
            confidence=observation.confidence,
        )

    prior_live = round(
        float(prior_live_commitment_bb or 0.0),
        4,
    )

    current_price = round(
        float(current_price_bb or 0.0),
        4,
    )

    target_live = round(
        prior_live + max(0.0, float(delta)),
        4,
    )

    if betting_open:
        if abs(delta) <= tolerance:
            return BoundaryActionResolution(
                street=street,
                seat=seat,
                action="FOLD",
                resolved=True,
                reason=(
                    "player still owed response to open aggression and "
                    "trusted boundary stack showed no additional commitment"
                ),
                confidence=observation.confidence,
            )

        if abs(target_live - current_price) <= tolerance:
            return BoundaryActionResolution(
                street=street,
                seat=seat,
                action="CALL",
                amount_bb=round(float(delta), 4),
                resolved=True,
                reason=(
                    "trusted boundary stack decrease brought live "
                    "commitment exactly to the closing price"
                ),
                confidence=observation.confidence,
            )

        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason=(
                "terminal commitment does not uniquely identify fold or call; "
                "raise/all-in reconstruction requires additional evidence"
            ),
            confidence=observation.confidence,
        )

    # No open aggression: a player owing traversal action can check only
    # postflop. Preflop contains blind-specific semantics and remains
    # deliberately unresolved here.
    if (
        street != "PREFLOP"
        and abs(delta) <= tolerance
    ):
        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action="CHECK",
            resolved=True,
            reason=(
                "player owed postflop traversal action, no aggression was "
                "open, and trusted boundary stack showed no commitment"
            ),
            confidence=observation.confidence,
        )

    return BoundaryActionResolution(
        street=street,
        seat=seat,
        action=None,
        resolved=False,
        reason="boundary evidence does not uniquely determine an action",
        confidence=observation.confidence,
    )
