from dataclasses import dataclass
from typing import Optional, Tuple

from src.v017.frame_hand_observer import (
    common_mode_stack_shift_seats,
)
from src.v017.stack_settlement_gate import (
    StackSettlement,
    StackSettlementGate,
)


@dataclass(frozen=True)
class QuantitativeTransactionResult:
    rejected_common_mode: Tuple[dict, ...]
    deferred: Tuple[dict, ...]
    settled: Tuple[StackSettlement, ...]
    admitted: Tuple[dict, ...]


def filter_common_mode_quantitative_events(events):
    quantitative = tuple(
        event
        for event in events
        if event.get("type")
        == "STACK_QUANTITATIVE_OBSERVATION"
    )

    rejected_seats = common_mode_stack_shift_seats(
        quantitative
    )

    eligible = tuple(
        event
        for event in quantitative
        if event.get("seat") not in rejected_seats
    )

    rejected = tuple(
        event
        for event in quantitative
        if event.get("seat") in rejected_seats
    )

    return eligible, rejected


def process_quantitative_frame(
    observer,
    settlement_gate,
    events,
):
    """
    Production quantitative authority transaction.

    Raw quantitative observations are physical evidence only.

    Complete-frame common-mode filtering happens before any
    observation may acquire settlement ownership. Surviving evidence
    then requires StackSettlementGate temporal confirmation before
    semantic admission.
    """
    eligible, rejected = (
        filter_common_mode_quantitative_events(
            events
        )
    )

    deferred = []
    settled_rows = []
    admitted_rows = []

    for event in eligible:
        seat = event.get("seat")

        has_commitment_evidence = bool(
            seat
            and seat
            in observer.confirmed_bet_regions
        )

        resolved_value = event.get(
            "resolved_value"
        )

        all_in_confirmed = bool(
            has_commitment_evidence
            and resolved_value is not None
            and abs(
                float(resolved_value)
            ) <= 0.02
        )

        settled = settlement_gate.observe(
            event,
            phase=observer.hand.street,
            has_commitment_evidence=(
                has_commitment_evidence
            ),
            all_in_confirmed=(
                all_in_confirmed
            ),
        )

        if settled is None:
            deferred.append(event)
            continue

        admitted = (
            observer.admit_quantitative_observation(
                event,
                all_in_confirmed=all_in_confirmed,
            )
        )

        settled_rows.append(settled)
        admitted_rows.extend(admitted)

        if admitted:
            observer.clear_quantitative_ownership(
                settled.seat
            )
            settlement_gate.clear_seat(
                settled.seat
            )

    return QuantitativeTransactionResult(
        rejected_common_mode=tuple(rejected),
        deferred=tuple(deferred),
        settled=tuple(settled_rows),
        admitted=tuple(admitted_rows),
    )
