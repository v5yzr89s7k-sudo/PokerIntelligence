"""
V0.17 asynchronous street-boundary identity contract.

Same-frame quantitative evidence must settle and publish immediately.

Slow board identity may begin asynchronously, but the authoritative
frame transaction must return without waiting for it.

The physical boundary remains owned by the outstanding async request
and is admitted only after that result becomes available.
"""

from pathlib import Path
from threading import Event

import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)

import src.v017.run_live_observer as live


PLAYERS = [
    {
        "seat": "raiser",
        "position": "BTN",
        "name": "Raiser",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def quantitative(frame, value):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "bb",
        "prior": 50.0,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "candidates": (
            (value, 1),
        ),
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": (
            50.0 - value
        ),
    }


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "raiser",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "raiser": 50.0,
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="async-boundary-deferral",
    )

    hand = observer.hand

    assert (
        hand.observe_stack_commitment(
            "raiser",
            2.0,
        )
        == "RAISE"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            1.5,
        )
        == "CALL"
    )

    assert hand.street == "PREFLOP"
    assert hand.next_actor == "bb"

    observer.trusted_stacks["bb"] = 50.0

    return observer


def main():
    observer = build_observer()
    state = live.FrameTransactionState()

    first = quantitative(
        20,
        49.0,
    )

    settled = state.settlement_gate.observe(
        first,
        phase=observer.hand.street,
        has_commitment_evidence=True,
    )

    assert settled is None

    events = (
        {
            "frame": 21,
            "type":
                "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 1,
        },
        quantitative(
            21,
            49.0,
        ),
    )

    original_process_frame = (
        observer.process_frame
    )

    original_board_reader = (
        live.read_board_identity
    )

    board_started = Event()
    release_board = Event()

    def fake_process_frame(
        image,
        frame_id,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        assert frame_id == 21

        return FrameObservationResult(
            frame_id=frame_id,
            events=events,
            changed=False,
            text=None,
        )

    def blocked_board_reader(
        frame_path,
        expected_count,
    ):
        assert expected_count == 3

        board_started.set()

        if not release_board.wait(
            timeout=5.0
        ):
            raise RuntimeError(
                "test board reader release timeout"
            )

        return [
            "Jd",
            "9s",
            "Tc",
        ]

    observer.process_frame = fake_process_frame
    live.read_board_identity = blocked_board_reader

    try:
        image = np.zeros(
            (
                696,
                934,
                3,
            ),
            dtype=np.uint8,
        )

        before_actions = len(
            observer.hand.actions
        )

        tx = live.process_frame_transaction(
            observer,
            image,
            Path(
                "/tmp/"
                "async_boundary_frame_21.png"
            ),
            21,
            state,
        )

        # Worker must have started, but transaction must have returned
        # while the worker is deliberately unresolved.
        assert board_started.wait(
            timeout=1.0
        )

        assert tx.outcome == "CONTINUE"

        new_actions = (
            observer.hand
            .semantic_actions()[
                before_actions:
            ]
        )

        assert len(new_actions) == 1
        assert new_actions[0]["seat"] == "bb"
        assert new_actions[0]["action"] == "CALL"

        # Action is canonical immediately, and physical board
        # evidence owns street chronology without waiting for the
        # deliberately blocked identity reader.
        assert observer.hand.street == "FLOP"
        assert observer.hand.board == []

        # Slow board request still owns the physical boundary.
        assert (
            state.board_identity_reader.future
            is not None
        )

        request = (
            state.board_identity_reader.request
        )

        assert request is not None
        assert (
            request["boundary_event"]["frame"]
            == 21
        )
        assert (
            request["boundary_event"]["type"]
            == "FLOP_BOUNDARY_PHYSICAL"
        )

        # No boundary was lost or admitted early.
        assert (
            state.pending_board_boundaries
            == []
        )

        print(
            "FRAME TRANSACTION RETURNED "
            "BEFORE BOARD IDENTITY: PASS"
        )

        print(
            "SAME-FRAME QUANTITATIVE ACTION "
            "PUBLISHED FIRST: PASS"
        )

        # Finish worker only after non-blocking behavior is proven.
        release_board.set()

        completed = None

        for _ in range(100):
            completed = (
                state.board_identity_reader
                .collect_ready()
            )

            if completed is not None:
                break

            Event().wait(0.01)

        assert completed is not None

        assert (
            live.apply_async_board_identity_result(
                observer,
                completed,
            )
            is True
        )

        assert observer.hand.street == "FLOP"
        assert observer.hand.board == [
            "Jd",
            "9s",
            "Tc",
        ]

        print(
            "ASYNC BOARD IDENTITY ATTACHMENT AFTER RESULT: PASS"
        )

        print(
            "V0.17 ASYNC BOARD FAST PATH: PASS"
        )

    finally:
        release_board.set()

        state.board_identity_reader.close()

        observer.process_frame = (
            original_process_frame
        )

        live.read_board_identity = (
            original_board_reader
        )


if __name__ == "__main__":
    main()
