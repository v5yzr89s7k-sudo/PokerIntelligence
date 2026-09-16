"""
Chronology completion rules for objective downstream evidence.

This module does NOT assign poker semantics.

It identifies which earlier actors must have completed an action
before a later actor/street can physically occur.

HandEngine alone determines what zero-chip completion means.
"""


def predecessors_before_actor(
    pending_to_act,
    observed_actor,
):
    pending = list(
        pending_to_act
    )

    if observed_actor not in pending:
        raise ValueError(
            "observed actor is outside pending chronology: "
            f"{observed_actor}"
        )

    index = pending.index(
        observed_actor
    )

    return pending[:index]


def remaining_before_street_boundary(
    pending_to_act,
):
    """
    A new board street cannot physically appear until the previous
    betting street has completed.

    Therefore every still-pending actor must already have completed
    action before the observed board boundary.
    """
    return list(
        pending_to_act
    )
