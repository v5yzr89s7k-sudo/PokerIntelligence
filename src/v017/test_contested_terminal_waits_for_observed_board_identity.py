"""
Regression for live Hand 7, 2026-10-16.

A contested winner may become objectively visible before the asynchronous
identity reader has finished an already-observed river.

The transaction must not expose HAND_COMPLETE until that physical board's
identity ownership has drained.

Uncontested completion must remain immediate.
"""

from concurrent.futures import Future

from src.v017.run_live_observer import (
    FrameTransactionState,
    terminal_publication_ready,
)


class DummyHand:
    def __init__(self):
        self.hand_complete = True
        self.completion_reason = "CONTESTED"
        self.street = "RIVER"
        self.board = ["5h", "Js", "6d", "5s"]


class DummyObserver:
    def __init__(self):
        self.hand = DummyHand()


def main():
    observer = DummyObserver()
    state = FrameTransactionState()

    try:
        # Hand 7 state at winner frame 871:
        # river was physically observed, but river identity was still
        # executing in the single asynchronous board lane.
        future = Future()
        state.board_identity_reader.future = future
        state.board_identity_reader.request = {
            "frame_path": "/tmp/hand7_river.png",
            "boundary_event": {
                "frame": 834,
                "type": "RIVER_BOUNDARY_PHYSICAL",
                "board_count": 5,
            },
            "expected_count": 5,
        }

        assert terminal_publication_ready(
            observer,
            state,
        ) is False, (
            "contested terminal escaped while observed "
            "river identity remained in flight"
        )

        # Once the identity has been attached, terminal publication may
        # complete normally.
        state.board_identity_reader.future = None
        state.board_identity_reader.request = None
        observer.hand.board = [
            "5h", "Js", "6d", "5s", "9h"
        ]

        assert terminal_publication_ready(
            observer,
            state,
        ) is True

        # Uncontested completion does not require a board runout.
        observer.hand.completion_reason = "UNCONTESTED"
        observer.hand.street = "PREFLOP"
        observer.hand.board = []

        future = Future()
        state.board_identity_reader.future = future

        assert terminal_publication_ready(
            observer,
            state,
        ) is True

        print(
            "CONTESTED TERMINAL WAITS FOR OBSERVED BOARD: PASS"
        )
        print(
            "UNCONTESTED TERMINAL REMAINS IMMEDIATE: PASS"
        )

    finally:
        # Avoid waiting on our deliberately unresolved synthetic future.
        state.board_identity_reader.future = None
        state.board_identity_reader.request = None
        state.board_identity_reader.close()


if __name__ == "__main__":
    main()
