"""
RED contract for the action-latency milestone.

A chronologically valid physical commitment must be publishable as
poker semantics before asynchronous quantitative stack settlement.

Stack settlement owns sizing/reconciliation, not existence of the action.
"""

import inspect

from src.api import api_event_state_machine as sm


def main():
    print("===== FAST COMMITMENT SEMANTIC CONTRACT =====")

    candidates = [
        "handle_actor_observed",
        "handle_live_commitment",
        "handle_physical_commitment",
    ]

    handler = None
    handler_name = None

    for name in candidates:
        candidate = getattr(
            sm,
            name,
            None,
        )

        if callable(candidate):
            handler = candidate
            handler_name = name
            break

    print(
        "candidate handler:",
        handler_name,
    )

    assert handler is not None, (
        "RED: no state-machine handler currently owns "
        "immediate physical commitment semantics"
    )

    source = inspect.getsource(handler)

    print()
    print("===== HANDLER =====")
    print(source)

    semantic_markers = (
        "BET_OR_RAISE",
        "CALL_OR_RAISE",
        "BET",
        "CALL",
        "commit",
        "action",
    )

    has_semantic_path = any(
        marker in source
        for marker in semantic_markers
    )

    assert has_semantic_path, (
        "RED: actor-observed handling does not publish "
        "semantic commitment before quantitative stack settlement"
    )

    stack_wait_markers = (
        "stack_update",
        "stack_candidate_closed",
        "validated_stack_transition",
    )

    requires_stack_completion = any(
        marker in source
        for marker in stack_wait_markers
    )

    assert not requires_stack_completion, (
        "RED: immediate commitment semantics still depend "
        "on settled-stack completion"
    )

    print()
    print(
        "PASS: physical commitment owns immediate semantics; "
        "stack settlement is reconciliation only"
    )


if __name__ == "__main__":
    main()
