"""
Production regression:
zero-stack + independent commitment evidence must propagate
all_in_confirmed through process_frame_transaction into HandEngine.

This marks only that player all-in. Other players remain normally
actionable when they still have chips and betting obligations.
"""

from pathlib import Path

import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)
import src.v017.run_live_observer as live


PLAYERS = [
    {
        "seat": "short",
        "position": "UTG",
        "name": "Short",
        "stack_bb": 5.0,
        "dealt_in": True,
    },
    {
        "seat": "deep",
        "position": "BTN",
        "name": "Deep",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "BB",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
]


def quantitative(frame):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "short",
        "prior": 5.0,
        "reader_value": 0.0,
        "resolved": True,
        "resolved_value": 0.0,
        "candidates": ((0.0, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 5.0,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["short", "deep", "hero"],
        small_blind_seat="deep",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "short": 5.0,
            "deep": 50.0,
            "hero": 50.0,
        },
        opponent_seats=["short", "deep"],
        quantitative_seats=["short"],
        hero_seat="hero",
        hand_id="production-allin-propagation",
    )

    # Independent physical evidence proves the zero-stack transition
    # represents chips committed, not OCR noise.
    observer.confirmed_bet_regions = {"short"}

    state = live.FrameTransactionState()

    original = observer.process_frame
    calls = {"count": 0}

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        calls["count"] += 1

        return FrameObservationResult(
            frame_id=frame_id,
            events=(quantitative(frame_id),),
            changed=False,
            text=None,
        )

    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (696, 934, 3),
            dtype=np.uint8,
        )

        # First observation arms temporal settlement.
        live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/allin_propagation.png"),
            10,
            state,
        )

        # Second independently confirms it.
        live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/allin_propagation.png"),
            11,
            state,
        )

        assert observer.hand.players["short"].all_in is True, (
            "RED: production settlement proved zero-stack all-in "
            "but all_in_confirmed was lost before HandEngine"
        )

        # Critical multiway contract:
        # one all-in player does NOT imply automatic runout.
        assert observer.hand.next_actor == "deep"
        assert "deep" in observer.hand.pending_to_act
        assert "hero" in observer.hand.pending_to_act

        print(
            "PRODUCTION ZERO-STACK ALL-IN AUTHORITY: PASS"
        )
        print(
            "MULTIWAY NON-ALL-IN PLAYERS REMAIN ACTIONABLE: PASS"
        )

    finally:
        state.board_identity_reader.close()
        observer.process_frame = original


if __name__ == "__main__":
    main()
