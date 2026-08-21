"""
Regression contract for the July 22 BTN preflop open.

Known production sequence:

    actor_observed seat_lower_right
    bet amount = 2.00 BB
    visual ActionEpisode closes
    asynchronous stack worker later validates:
        58.55 -> 56.55
        delta = 2.00 BB

The coordinator publishes stack_update, but the corresponding
STACK_CHANGED observation never reaches ActionEpisodeManager.

This test remains deliberately RED until the exact production
transport seam is identified below. Do not implement a parallel
semantic path here.
"""

from pathlib import Path


def main():
    source = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    assert (
        "changes.stack_changed_seats = settled_seats"
        in source
    )

    assert (
        "changes.stack_change_details = settled_details"
        in source
    )

    assert (
        "observer.ingest_changes"
        in source
    )

    raise AssertionError(
        "REPRODUCED: validated asynchronous stack result can "
        "publish stack_update without a guaranteed STACK_CHANGED "
        "observation pass through observer -> episode_manager"
    )


if __name__ == "__main__":
    main()
