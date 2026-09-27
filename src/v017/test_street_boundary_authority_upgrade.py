"""
Regression: retained physical street-boundary authority must upgrade
monotonically when stronger evidence arrives for the same boundary.

A boundary first retained with complete_pending=False must become
complete_pending=True when the same physical (frame, type) boundary is
later confirmed by authoritative board identity.

The reverse observation must never downgrade True back to False.
"""

from src.v017.frame_hand_observer import FrameHandObserver


def boundary():
    return {
        "frame": 154,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
        "previous_board_count": 1,
    }


def main():
    observer = object.__new__(
        FrameHandObserver
    )

    observer.pending_street_boundaries = []

    class Hand:
        street = "PREFLOP"
        next_actor = "seat_mid_right"

    observer.hand = Hand()

    order = [
        "seat_mid_right",
        "hero",
    ]

    board = [
        "As",
        "Kd",
        "7c",
    ]

    observer._retain_pending_street_boundary(
        boundary(),
        action_order=order,
        board=board,
        complete_pending=False,
    )

    assert len(
        observer.pending_street_boundaries
    ) == 1

    retained = (
        observer.pending_street_boundaries[0]
    )

    assert retained["complete_pending"] is False

    print(
        "initial_complete_pending =",
        retained["complete_pending"],
    )

    observer._retain_pending_street_boundary(
        boundary(),
        action_order=order,
        board=board,
        complete_pending=True,
    )

    assert len(
        observer.pending_street_boundaries
    ) == 1

    retained = (
        observer.pending_street_boundaries[0]
    )

    print(
        "upgraded_complete_pending =",
        retained["complete_pending"],
    )

    assert retained["complete_pending"] is True, (
        "same physical boundary discarded stronger "
        "complete_pending authority"
    )

    observer._retain_pending_street_boundary(
        boundary(),
        action_order=order,
        board=board,
        complete_pending=False,
    )

    retained = (
        observer.pending_street_boundaries[0]
    )

    print(
        "after_weaker_duplicate =",
        retained["complete_pending"],
    )

    assert retained["complete_pending"] is True, (
        "boundary authority was downgraded"
    )

    print(
        "V0.17 STREET BOUNDARY AUTHORITY UPGRADE: PASS"
    )


if __name__ == "__main__":
    main()
