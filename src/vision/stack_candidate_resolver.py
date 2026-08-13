from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class StackCandidateResolution:
    value: Optional[float]
    resolved: bool
    reason: str
    distance: Optional[float] = None


def resolve_stack_candidates(
    candidates: Iterable[float],
    *,
    previous_stack_bb: Optional[float] = None,
    maximum_drop_bb: Optional[float] = None,
    tolerance: float = 0.05,
) -> StackCandidateResolution:
    """
    Resolve OCR stack candidates using only numeric continuity.

    This layer knows nothing about seats, positions, actions, bets,
    Replay fixtures, or poker semantics.

    Without a previous trusted stack, disagreement remains unresolved.

    With a previous trusted stack:
      - stack increases are not eligible as wager transitions;
      - exact/near previous-stack candidates are preferred;
      - otherwise choose the closest non-increasing candidate;
      - an optional maximum-drop bound may reject implausibly large changes.

    OCR-family vote counts are deliberately not treated as independent
    evidence here.
    """
    values = []

    for candidate in candidates or []:
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            continue

        if value <= 0.0:
            continue

        if not any(abs(value - existing) <= tolerance for existing in values):
            values.append(value)

    if not values:
        return StackCandidateResolution(
            value=None,
            resolved=False,
            reason="no_numeric_candidates",
        )

    if previous_stack_bb is None:
        if len(values) == 1:
            return StackCandidateResolution(
                value=values[0],
                resolved=True,
                reason="single_candidate_without_baseline",
                distance=None,
            )

        return StackCandidateResolution(
            value=None,
            resolved=False,
            reason="candidate_disagreement_without_baseline",
            distance=None,
        )

    previous = float(previous_stack_bb)

    eligible = [
        value
        for value in values
        if value <= previous + tolerance
    ]

    if not eligible:
        return StackCandidateResolution(
            value=None,
            resolved=False,
            reason="all_candidates_increase_stack",
            distance=None,
        )

    selected = min(
        eligible,
        key=lambda value: abs(previous - value),
    )

    distance = abs(previous - selected)

    if (
        maximum_drop_bb is not None
        and distance > float(maximum_drop_bb)
    ):
        return StackCandidateResolution(
            value=None,
            resolved=False,
            reason="nearest_candidate_exceeds_drop_bound",
            distance=distance,
        )

    return StackCandidateResolution(
        value=selected,
        resolved=True,
        reason="nearest_nonincreasing_candidate",
        distance=distance,
    )
