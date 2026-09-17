"""
Minimal v0.17 quantitative settlement gate.

Physical OCR observations are evidence only.

A proposed post-action stack becomes settled only when:
1. the read satisfies the trusted OCR contract;
2. the same proposed value is independently observed on a later frame;
3. the transition validator accepts it.

This module owns no poker semantics.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from src.api.stack_transition_validator import (
    ACCEPT,
    validate_stack_transition,
)


VALUE_TOLERANCE_BB = 0.02
MINIMUM_CONFIDENCE = 0.95
MINIMUM_VOTES = 2


@dataclass
class PendingStackSettlement:
    value: float
    first_frame: object
    confirmations: int = 1


@dataclass(frozen=True)
class StackSettlement:
    seat: str
    prior: float
    value: float
    delta_bb: float
    frame: object


class StackSettlementGate:

    def __init__(self):
        self.pending: Dict[
            str,
            PendingStackSettlement,
        ] = {}

    def clear_seat(self, seat):
        self.pending.pop(
            str(seat),
            None,
        )

    def observe(
        self,
        observation,
        *,
        phase,
        has_commitment_evidence=False,
        all_in_confirmed=False,
    ) -> Optional[StackSettlement]:

        if (
            observation.get("type")
            != "STACK_QUANTITATIVE_OBSERVATION"
        ):
            return None

        if not observation.get("resolved"):
            return None

        value = observation.get(
            "resolved_value"
        )

        prior = observation.get(
            "prior"
        )

        if value is None or prior is None:
            return None

        confidence = float(
            observation.get("confidence")
            or 0.0
        )

        votes = int(
            observation.get("votes")
            or 0
        )

        # Observation-level authority is reader-contract aware.
        #
        # Legacy OCR requires within-frame consensus.
        #
        # native_green_fast has already passed strict structural
        # numeric validation, but intentionally represents one
        # physical OCR observation (confidence=.80 / votes=1).
        # It may therefore participate in the candidate epoch.
        #
        # This does NOT make one native observation sufficient for
        # settlement: the independent later-frame confirmation below
        # remains mandatory.
        consensus_authority = (
            confidence >= MINIMUM_CONFIDENCE
            and votes >= MINIMUM_VOTES
        )

        native_fast_authority = (
            observation.get("mode")
            == "native_green_fast"
        )

        # A native zero-stack display is a special physical state.
        #
        # Tesseract may clearly expose raw "0 BB" while the normal
        # native quantitative reader deliberately leaves that read
        # unresolved (confidence=0 / votes=0 /
        # mode=native_fast_unresolved). resolve_fast_stack may still
        # recover exactly 0.0 from that raw candidate.
        #
        # Such an unresolved zero may participate in a settlement
        # candidate epoch ONLY when the independent same-seat chip
        # sensor has already confirmed the all-in condition.
        #
        # This does not authorize arbitrary unresolved OCR and does
        # not make one zero observation sufficient for settlement.
        physically_confirmed_zero_authority = bool(
            all_in_confirmed
            and value is not None
            and abs(float(value)) <= VALUE_TOLERANCE_BB
            and observation.get("mode")
            == "native_fast_unresolved"
            and tuple(
                observation.get("candidates")
                or ()
            )
            == ((0.0, 1),)
        )

        if not (
            consensus_authority
            or native_fast_authority
            or physically_confirmed_zero_authority
        ):
            return None

        seat = str(
            observation["seat"]
        )

        value = float(value)
        prior = float(prior)
        frame = observation.get("frame")

        candidate = self.pending.get(
            seat
        )

        if candidate is None:
            self.pending[seat] = (
                PendingStackSettlement(
                    value=value,
                    first_frame=frame,
                )
            )
            return None

        # Same source frame is not independent confirmation.
        if frame == candidate.first_frame:
            return None

        if (
            abs(
                value
                - candidate.value
            )
            > VALUE_TOLERANCE_BB
        ):
            # Contradiction starts a new candidate epoch.
            self.pending[seat] = (
                PendingStackSettlement(
                    value=value,
                    first_frame=frame,
                )
            )
            return None

        # Reaching this point means the current value has matched
        # the pending candidate on a different source frame.
        #
        # For native_green_fast, that independent temporal agreement
        # is the consensus evidence required by the transition
        # validator. Preserve the individual OCR metadata everywhere
        # else; only the validator-facing aggregate evidence is
        # promoted.
        validation_confidence = confidence
        validation_votes = votes

        if (
            native_fast_authority
            or physically_confirmed_zero_authority
        ):
            validation_confidence = max(
                validation_confidence,
                MINIMUM_CONFIDENCE,
            )
            validation_votes = max(
                validation_votes,
                MINIMUM_VOTES,
            )

        validation = validate_stack_transition(
            prior,
            value,
            confidence=validation_confidence,
            votes=validation_votes,
            phase=phase,
            has_commitment_evidence=(
                has_commitment_evidence
            ),
            all_in_confirmed=(
                all_in_confirmed
            ),
        )

        if validation.decision != ACCEPT:
            return None

        self.pending.pop(
            seat,
            None,
        )

        return StackSettlement(
            seat=seat,
            prior=prior,
            value=value,
            delta_bb=validation.delta_bb,
            frame=frame,
        )
