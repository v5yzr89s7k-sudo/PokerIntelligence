"""
Production-path regression for the 2026-10-07 live certification crash.

Live evidence:
    semantic street: PREFLOP
    physical board: 0 -> 5 in one sampled frame
    detector event:
        FLOP_BOUNDARY_PHYSICAL
        previous_board_count=0
        board_count=5
    quantitative settlement ownership still pending

The real process_frame_transaction() must normalize the sampled jump
into strict FLOP/3, TURN/4, RIVER/5 boundary ownership and must not
raise the former strict-boundary ValueError.
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
        "seat": "villain",
        "position": "UTG",
        "name": "Villain",
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
        "seat": "villain",
        "prior": 50.0,
        "reader_value": 48.0,
        "resolved": True,
        "resolved_value": 48.0,
        "candidates": ((48.0, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 2.0,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["villain", "hero"],
        small_blind_seat="hero",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "villain": 50.0,
            "hero": 50.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=["villain"],
        hero_seat="hero",
        hand_id="live-board-jump-production",
    )

    # Close betting legitimately before the physical board jump.
    #
    # Both players are independently confirmed all-in. HandEngine
    # therefore owns next_actor=None and no future street has betting
    # actionability.
    assert observer.hand.observe_stack_commitment(
        "villain",
        49.0,
        all_in_confirmed=True,
    ) == "RAISE"

    assert observer.hand.observe_stack_commitment(
        "hero",
        48.0,
        all_in_confirmed=True,
    ) == "CALL"

    assert observer.hand.next_actor is None
    assert observer.hand.pending_to_act == []

    state = live.FrameTransactionState()

    events = (
        quantitative(248),
        {
            "frame": 248,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 5,
            "previous_board_count": 0,
        },
    )

    actions_before_transaction = tuple(
        observer.hand.semantic_actions()
    )

    original = observer.process_frame

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        return FrameObservationResult(
            frame_id=frame_id,
            events=events,
            changed=False,
            text=None,
        )

    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (696, 934, 3),
            dtype=np.uint8,
        )

        tx = live.process_frame_transaction(
            observer,
            image,
            Path("/tmp/live_board_jump_248.png"),
            248,
            state,
        )

        assert tx.outcome == "CONTINUE"

        # Synthetic quantitative evidence deliberately leaves stale
        # settlement ownership behind after betting has already closed.
        assert "villain" in state.settlement_gate.pending

        # RED CONTRACT:
        # stale settlement ownership has no authority to hold automatic
        # all-in board runout behind the betting street.
        assert observer.hand.street == "RIVER", (
            "RED: all-in board runout blocked by stale "
            "quantitative settlement ownership"
        )

        assert observer.hand.next_actor is None
        assert observer.hand.pending_to_act == []

        retained = [
            (
                row["observation"]["type"],
                row["observation"]["board_count"],
                row["observation"]["frame"],
            )
            for row in observer.pending_street_boundaries
        ]

        expected = [
            ("FLOP_BOUNDARY_PHYSICAL", 3, 248),
            ("TURN_BOUNDARY_PHYSICAL", 4, 248),
            ("RIVER_BOUNDARY_PHYSICAL", 5, 248),
        ]

        print("retained =", retained)
        print("expected =", expected)

        assert retained == [], (
            "RED: automatic all-in runout boundaries remain "
            f"semantically retained: {retained}"
        )

        # The automatic board runout must add no betting semantics.
        # The legitimate preflop all-in RAISE/CALL existed before this
        # transaction and must remain unchanged.
        actions_after_transaction = tuple(
            observer.hand.semantic_actions()
        )

        assert (
            actions_after_transaction
            == actions_before_transaction
        ), (
            "automatic all-in board runout fabricated "
            "betting actions"
        )

        print("FORMER VALUEERROR: NO")
        print("STRICT BOUNDARIES RETAINED: 3")
        print("FABRICATED BETTING ACTIONS: NO")
        print(
            "V0.17 LIVE BOARD JUMP "
            "PRODUCTION TRANSACTION: PASS"
        )

    finally:
        state.board_identity_reader.close()
        observer.process_frame = original


if __name__ == "__main__":
    main()
