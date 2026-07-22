from dataclasses import dataclass
from typing import Optional


ACCEPT = "accept"
RETRY = "retry"
REJECT = "reject"


@dataclass(frozen=True)
class StackTransitionValidation:
    decision: str
    reason: str
    previous_stack_bb: float
    current_stack_bb: float
    delta_bb: float
    large_commitment: bool


def validate_stack_transition(
    previous_stack_bb: float,
    current_stack_bb: float,
    *,
    confidence: float,
    votes: int,
    phase: str,
    has_commitment_evidence: bool = False,
    all_in_confirmed: bool = False,
    minimum_confidence: float = 0.95,
    minimum_votes: int = 2,
) -> StackTransitionValidation:
    """
    Validate a proposed quantitative stack transition before CanonicalHand
    is mutated.

    The validator does not infer an action. It only decides whether the
    proposed stack change is sufficiently plausible to publish.

    Decisions:
      accept:
        The transition can be emitted as a stack_update.

      retry:
        Preserve the pending transition and obtain another OCR observation.

      reject:
        The transition is structurally incompatible with a wager.
    """
    previous = float(previous_stack_bb)
    current = float(current_stack_bb)
    confidence = float(confidence)
    votes = int(votes)
    phase = str(phase or "WAITING").upper()

    delta = round(previous - current, 2)

    # Stack increases are not new wagers. Returned chips and corrected pots
    # must be handled by explicit reconciliation logic, not stack settlement.
    if delta < 0.0:
        return StackTransitionValidation(
            decision=REJECT,
            reason="stack_increase",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=False,
        )

    if delta == 0.0:
        return StackTransitionValidation(
            decision=REJECT,
            reason="no_stack_change",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=False,
        )

    # A zero stack is potentially legitimate only when an independent signal
    # confirms that the player is all-in.
    if current <= 0.0 and not all_in_confirmed:
        return StackTransitionValidation(
            decision=RETRY,
            reason="zero_without_all_in_confirmation",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=True,
        )

    if confidence < minimum_confidence or votes < minimum_votes:
        return StackTransitionValidation(
            decision=RETRY,
            reason="untrusted_ocr",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=False,
        )

    # Treat a transition as unusually large when it removes at least half of
    # the prior stack and at least 8 BB. This catches decimal-collapse OCR
    # errors such as 20.12 -> 2.00 without delaying ordinary bets and raises.
    large_threshold = max(8.0, previous * 0.50)
    large_commitment = delta >= large_threshold

    # During WAITING there is not yet a reliable betting context capable of
    # supporting a very large voluntary commitment.
    if large_commitment and phase == "WAITING":
        return StackTransitionValidation(
            decision=RETRY,
            reason="large_commitment_before_active_hand",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=True,
        )

    # A large stack collapse needs independent table evidence. OCR confidence
    # alone is insufficient because multiple preprocessing variants can agree
    # on the same missing decimal point.
    if (
        large_commitment
        and not has_commitment_evidence
        and not all_in_confirmed
    ):
        return StackTransitionValidation(
            decision=RETRY,
            reason="large_commitment_without_evidence",
            previous_stack_bb=previous,
            current_stack_bb=current,
            delta_bb=delta,
            large_commitment=True,
        )

    return StackTransitionValidation(
        decision=ACCEPT,
        reason="plausible_stack_commitment",
        previous_stack_bb=previous,
        current_stack_bb=current,
        delta_bb=delta,
        large_commitment=large_commitment,
    )
