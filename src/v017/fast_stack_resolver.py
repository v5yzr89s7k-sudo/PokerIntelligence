"""
Prior-aware fast stack resolution.

Consumes candidates already observed by the normal stack reader.

STRICT RULES:
    - no OCR is performed here
    - no candidate is invented
    - no decimal scaling/correction
    - impossible stack increases are rejected
    - no poker semantics are assigned
"""

from collections import Counter
from dataclasses import dataclass
from typing import Optional, Tuple


EPSILON = 0.02


@dataclass(frozen=True)
class FastStackResolution:
    resolved: bool
    value: Optional[float]
    support: int
    reason: str
    candidates: Tuple[Tuple[float, int], ...]


def resolve_fast_stack(
    reading,
    prior_value,
):
    prior = float(
        prior_value
    )

    plausible = []

    for row in (
        reading.get("raw")
        or []
    ):
        value = row.get(
            "stack_bb"
        )

        if value is None:
            continue

        value = round(
            float(value),
            2,
        )

        # A stack under observation may remain unchanged or decrease.
        # An increase cannot represent a chip commitment.
        if (
            0.0
            <= value
            <= prior + EPSILON
        ):
            plausible.append(
                value
            )

    if not plausible:
        return FastStackResolution(
            resolved=False,
            value=None,
            support=0,
            reason="no_plausible_observed_candidate",
            candidates=(),
        )

    counts = Counter(
        plausible
    )

    ranked = tuple(
        sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                abs(
                    prior
                    - item[0]
                ),
                item[0],
            ),
        )
    )

    best_value, best_support = (
        ranked[0]
    )

    tied = [
        value
        for value, support
        in ranked
        if support == best_support
    ]

    if len(tied) != 1:
        return FastStackResolution(
            resolved=False,
            value=None,
            support=best_support,
            reason="plausible_candidate_tie",
            candidates=ranked,
        )

    return FastStackResolution(
        resolved=True,
        value=float(
            best_value
        ),
        support=int(
            best_support
        ),
        reason="prior_aware_raw_consensus",
        candidates=ranked,
    )
