"""
Live Hand 7 regression — 2026-10-16.

Physical chronology had already reached RIVER, but asynchronous board
identity still owned the fifth card when winner evidence appeared.

Production process_frame_transaction() must:

    winner visible + contested hand + RIVER + incomplete canonical board
    + river identity still in flight
        -> CONTINUE

It must not expose HAND_COMPLETE until the already-observed river
identity has been attached.

This test owns the production terminal transaction boundary. It does
not synchronously wait for the worker.
"""

from concurrent.futures import Future
from pathlib import Path

import cv2

import src.v017.run_live_observer as live

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
    },
]


def build_incomplete_river():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="hand7-terminal-board-race",
    )

    hand = observer.hand

    # We only need the terminal state contract here. Physical street
    # chronology has already established RIVER, while async identity
    # is one card behind.
    hand.street = "RIVER"
    hand.board = [
        "4d",
        "Qs",
        "Ah",
        "8s",
    ]

    hand.pending_to_act = []
    hand.current_price_bb = 0.0

    return observer


def main():
    root = Path(
        "runtime/pixel_lab/observer_input/"
        "controlled_hand_2826921615"
    )

    # Existing controlled frame with authentic winner evidence.
    frame36_path = root / "frame_0036.png"
    frame36 = cv2.imread(
        str(frame36_path)
    )

    assert frame36 is not None

    observer = build_incomplete_river()
    state = live.FrameTransactionState()

    original_process_frame = observer.process_frame

    # Prevent unrelated physical detector evidence from altering the
    # synthetic Hand-7 terminal state. Winner detection remains the
    # real production detector on the real controlled image.
    def no_new_frame_events(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        return FrameObservationResult(
            frame_id=frame_id,
            events=(),
            changed=False,
            text=None,
        )

    observer.process_frame = no_new_frame_events

    try:
        # Synthetic transport ownership corresponding to Hand 7:
        # river was physically observed, but identity has not returned.
        future = Future()

        state.board_identity_reader.future = future
        state.board_identity_reader.request = {
            "frame_path": frame36_path,
            "boundary_event": {
                "frame": 834,
                "type": "RIVER_BOUNDARY_PHYSICAL",
                "board_count": 5,
                "previous_board_count": 4,
            },
            "expected_count": 5,
        }

        tx = live.process_frame_transaction(
            observer,
            frame36,
            frame36_path,
            871,
            state,
        )

        assert observer.hand.hand_complete is True, (
            "winner evidence did not become authoritative"
        )

        assert (
            observer.hand.completion_reason
            == "CONTESTED"
        )

        assert observer.hand.street == "RIVER"

        assert len(observer.hand.board) == 4

        assert tx.outcome == "CONTINUE", (
            "RED: production escaped HAND_COMPLETE "
            "before river identity settled"
        )

        assert (
            state.board_identity_reader.future
            is future
        )

        print(
            "HAND 7 WINNER + INFLIGHT RIVER -> CONTINUE: PASS"
        )

        # Model completion of the already-owned asynchronous result.
        #
        # Do not call the external board reader. Supply the completed
        # transport result directly through the production finalizer.
        state.board_identity_reader.future = None
        state.board_identity_reader.request = None

        completed = {
            "request": {
                "frame_path": frame36_path,
                "boundary_event": {
                    "frame": 834,
                    "type": "RIVER_BOUNDARY_PHYSICAL",
                    "board_count": 5,
                    "previous_board_count": 4,
                },
                "expected_count": 5,
            },
            "board": [
                "4d",
                "Qs",
                "Ah",
                "8s",
                "3c",
            ],
            "error": None,
        }

        finalized = (
            live.finalize_async_board_identity_result(
                observer,
                state,
                completed,
                publication_frame=872,
            )
        )

        assert finalized["applied"] is True

        assert observer.hand.board == [
            "4d",
            "Qs",
            "Ah",
            "8s",
            "3c",
        ]

        assert live.terminal_publication_ready(
            observer,
            state,
        ) is True

        # Next production transaction may now expose completion.
        tx2 = live.process_frame_transaction(
            observer,
            frame36,
            frame36_path,
            872,
            state,
        )

        assert tx2.outcome == "HAND_COMPLETE", (
            "completed five-card contested hand did not "
            "leave terminal barrier"
        )

        assert len(observer.hand.board) == 5

        print(
            "HAND 7 RIVER IDENTITY ATTACHED BEFORE COMPLETION: PASS"
        )
        print(
            "HAND 7 PRODUCTION TERMINAL RACE: PASS"
        )

    finally:
        state.board_identity_reader.future = None
        state.board_identity_reader.request = None
        state.board_identity_reader.close()
        observer.process_frame = original_process_frame


if __name__ == "__main__":
    main()
