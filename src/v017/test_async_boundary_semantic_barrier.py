"""
Post-boundary frames cannot receive stale prior-street semantics while
board identity is unresolved. Capture remains non-blocking.
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


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="async-semantic-barrier",
    )

    # Close preflop legally: Hero completes the SB, then BB checks.
    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    observer.hand.observe_no_commitment("bb")

    assert observer.hand.next_actor is None

    state = live.FrameTransactionState()

    boundary = {
        "frame": 10,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
        "previous_board_count": 0,
    }

    calls = []

    def fake_process_frame(
        image,
        frame_id,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        calls.append(frame_id)

        if frame_id == 10:
            events = (boundary,)
        else:
            events = ()

        return FrameObservationResult(
            frame_id=frame_id,
            events=events,
            changed=False,
            text=None,
        )

    original = observer.process_frame
    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (2168, 3456, 3),
            dtype=np.uint8,
        )

        first = live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/frame_10.png"),
            10,
            state,
        )

        assert first.outcome == "CONTINUE"
        assert observer.hand.street == "PREFLOP"

        second = live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/frame_11.png"),
            11,
            state,
        )

        assert second.outcome == "CONTINUE"

        # Frame 11 must not enter stale PREFLOP semantic processing.
        assert calls == [10], (
            "post-boundary frame entered stale semantic processing "
            "before board identity resolved"
        )

        assert len(
            state.deferred_semantic_frames
        ) == 1

        deferred = state.deferred_semantic_frames[0]

        assert deferred["frame_id"] == 11
        assert deferred["frame_path"] == Path(
            "/tmp/frame_11.png"
        )

        print("CAPTURE BLOCKED: NO")
        print("STALE PREFLOP SEMANTICS: NO")
        print("POST-BOUNDARY FRAME DEFERRED: PASS")
        print("V0.17 ASYNC BOUNDARY SEMANTIC BARRIER: PASS")

    finally:
        observer.process_frame = original
        state.board_identity_reader.close()


if __name__ == "__main__":
    main()
