"""
Production regression for stale old-hand ownership after river clear.

A physical 5 -> 0 board transition after canonical RIVER proves that
the physical hand has ended.

It does NOT prove:
- CALL
- FOLD
- winner
- canonical HandEngine completion

Required production outcome:
    PHYSICAL_HAND_ENDED

That outcome relinquishes the old observer session without fabricating
poker semantics.
"""

from pathlib import Path

import numpy as np

import src.v017.run_live_observer as live

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)


PLAYERS = [
    {
        "seat": "villain",
        "position": "BB",
        "name": "Villain",
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
]


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["villain", "hero"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "villain": 50.0,
            "hero": 50.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=[
            "villain",
            "hero",
        ],
        hero_seat="hero",
        hand_id="river-board-clear-lifecycle",
    )

    observer.hand.street = "RIVER"
    observer.hand.board = [
        "7d",
        "Qc",
        "Ac",
        "3d",
        "Kd",
    ]

    # Reproduce the live stale chronology:
    # canonical river still believes Villain owns action.
    observer.hand.pending_to_act = [
        "villain",
    ]

    observer.previous_board_count = 5

    return observer


def main():
    observer = build_observer()
    state = live.FrameTransactionState()

    image = np.zeros(
        (32, 32, 3),
        dtype=np.uint8,
    )

    frame_path = Path(
        "/tmp/pi_river_board_clear.png"
    )

    before = list(
        observer.hand.semantic_actions()
    )

    original = observer.process_frame

    def physical_clear(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        return FrameObservationResult(
            frame_id=frame_id,
            events=(
                {
                    "frame": frame_id,
                    "type": "RIVER_BOARD_CLEARED_PHYSICAL",
                    "previous_board_count": 5,
                    "board_count": 0,
                },
            ),
            changed=False,
            text=None,
        )

    observer.process_frame = physical_clear

    try:
        tx = live.process_frame_transaction(
            observer,
            image,
            frame_path,
            390,
            state,
        )
    finally:
        observer.process_frame = original
        state.board_identity_reader.close()

    after = list(
        observer.hand.semantic_actions()
    )

    assert after == before, (
        "physical board clear fabricated "
        "a poker action"
    )

    assert observer.hand.winner_seats == [], (
        "physical board clear fabricated "
        "a winner"
    )

    assert observer.hand.hand_complete is False, (
        "physical board clear corrupted "
        "canonical result ownership"
    )

    assert observer.hand.completion_reason is None, (
        observer.hand.completion_reason
    )

    assert tx.outcome == "PHYSICAL_HAND_ENDED", (
        "RED: physical river clear did not "
        "relinquish stale old-hand ownership; "
        f"outcome={tx.outcome!r}"
    )

    print(
        "RIVER BOARD CLEAR FABRICATED ACTION: NO"
    )
    print(
        "RIVER BOARD CLEAR FABRICATED WINNER: NO"
    )
    print(
        "CANONICAL HAND COMPLETE FABRICATED: NO"
    )
    print(
        "OLD OBSERVER SESSION RELINQUISHED: YES"
    )
    print(
        "V0.17 RIVER BOARD-CLEAR "
        "TRANSACTION LIFECYCLE: PASS"
    )


if __name__ == "__main__":
    main()
