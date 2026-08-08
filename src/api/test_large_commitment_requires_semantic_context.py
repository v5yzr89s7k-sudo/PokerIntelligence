from src.api.stack_transition_validator import (
    RETRY,
    ACCEPT,
    validate_stack_transition,
)

# Large collapse with no semantic commitment.
result = validate_stack_transition(
    previous_stack_bb=96.0,
    current_stack_bb=9.86,
    confidence=0.98,
    votes=2,
    phase="PREFLOP",
    has_commitment_evidence=False,
)

assert result.decision == RETRY

# Same transition becomes acceptable only when semantic commitment exists.
result = validate_stack_transition(
    previous_stack_bb=96.0,
    current_stack_bb=9.86,
    confidence=0.98,
    votes=2,
    phase="PREFLOP",
    has_commitment_evidence=True,
)

assert result.decision == ACCEPT

print("Semantic commitment validator regression passed.")
