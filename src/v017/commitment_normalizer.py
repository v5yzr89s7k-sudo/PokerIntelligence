"""
Normalize physical stack-delta measurements against authoritative
betting state.

This module does NOT assign poker actions.

It may reconcile a tiny display/OCR discrepancy when the observed
physical commitment is effectively equal to the exact amount required
to reach the current authoritative price.
"""

from dataclasses import dataclass


DISPLAY_TOLERANCE_BB = 0.02


@dataclass(frozen=True)
class CommitmentMeasurement:
    observed_delta_bb: float
    normalized_delta_bb: float
    snapped_to_call_price: bool


def normalize_commitment_delta(
    observed_delta_bb,
    prior_street_commitment_bb,
    current_price_bb,
):
    observed = float(
        observed_delta_bb
    )

    prior = float(
        prior_street_commitment_bb
    )

    price = float(
        current_price_bb
    )

    if observed <= 0:
        raise ValueError(
            "observed commitment must be positive"
        )

    required_to_call = max(
        0.0,
        price - prior,
    )

    # Only reconcile against an already-established positive price.
    # An opening wager is never altered by this rule.
    if (
        price > 0.0
        and required_to_call > 0.0
        and abs(
            observed
            - required_to_call
        ) <= DISPLAY_TOLERANCE_BB
    ):
        return CommitmentMeasurement(
            observed_delta_bb=observed,
            normalized_delta_bb=required_to_call,
            snapped_to_call_price=True,
        )

    return CommitmentMeasurement(
        observed_delta_bb=observed,
        normalized_delta_bb=observed,
        snapped_to_call_price=False,
    )
