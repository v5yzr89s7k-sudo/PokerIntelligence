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
        hand_id="deferred-frame-replay",
    )

    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    observer.hand.observe_no_commitment("bb")

    state = live.FrameTransactionState()

    image = np.zeros(
        (2168, 3456, 3),
        dtype=np.uint8,
    )

    calls = []

    def fake_process_frame(
        image,
        frame_id,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        calls.append(
            (
                frame_id,
                observer.hand.street,
            )
        )

        return FrameObservationResult(
            frame_id=frame_id,
            events=(),
            changed=False,
            text=None,
        )

    original = observer.process_frame
    observer.process_frame = fake_process_frame

    try:
        state.unresolved_board_boundary = {
            "frame_path": Path("/tmp/frame_10.png"),
            "boundary_event": {
                "frame": 10,
                "type": "FLOP_BOUNDARY_PHYSICAL",
                "board_count": 3,
                "previous_board_count": 0,
            },
            "expected_count": 3,
        }

        for frame_id in (11, 12):
            tx = live.process_frame_transaction(
                observer,
                image,
                Path(f"/tmp/frame_{frame_id}.png"),
                frame_id,
                state,
            )

            assert tx.outcome == "CONTINUE"

        assert calls == []
        assert [
            row["frame_id"]
            for row in state.deferred_semantic_frames
        ] == [11, 12]

        completed = {
            "request": {
                "frame_path": Path("/tmp/frame_10.png"),
                "boundary_event": {
                    "frame": 10,
                    "type": "FLOP_BOUNDARY_PHYSICAL",
                    "board_count": 3,
                    "previous_board_count": 0,
                },
                "expected_count": 3,
            },
            "board": ["Jd", "9s", "Tc"],
            "error": None,
        }

        finalized = (
            live.finalize_async_board_identity_result(
                observer,
                state,
                completed,
                publication_frame=10,
            )
        )

        assert finalized["applied"] is True
        assert observer.hand.street == "FLOP"

        assert calls == [
            (11, "FLOP"),
            (12, "FLOP"),
        ], (
            "deferred frames were not replayed "
            "in original order under FLOP authority"
        )

        assert state.deferred_semantic_frames == []

        print("DEFERRED ORDER: 11 -> 12")
        print("REPLAY STREET: FLOP")
        print("DEFERRED QUEUE DRAINED: PASS")
        print("V0.17 DEFERRED SEMANTIC FRAME REPLAY: PASS")

    finally:
        observer.process_frame = original
        state.board_identity_reader.close()


if __name__ == "__main__":
    main()
