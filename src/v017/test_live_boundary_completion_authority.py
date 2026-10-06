"""
Regression for the Oct 6 live retained-boundary deadlock.

Production condition:

* a physical FLOP is retained while old-street quantitative ownership
  still exists;
* that quantitative ownership later expires without yielding another
  semantic action;
* no independent evidence exists from which CALL versus FOLD can be
  inferred;
* the retained physical FLOP must then acquire completion authority
  automatically;
* the boundary must advance PREFLOP -> FLOP without manufacturing a
  non-zero CALL/FOLD action.
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


def frame_result(frame_id, events):
    return FrameObservationResult(
        frame_id=frame_id,
        events=tuple(events),
        changed=False,
        text=None,
    )


def run_transaction(observer, state, frame_id, events):
    original = observer.process_frame

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        return frame_result(frame_id, events)

    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (696, 934, 3),
            dtype=np.uint8,
        )

        return live.process_frame_transaction(
            observer,
            image,
            Path(
                f"/tmp/live_boundary_completion_{frame_id}.png"
            ),
            frame_id,
            state,
        )
    finally:
        observer.process_frame = original


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
        hand_id="live-boundary-completion-authority",
    )

    state = live.FrameTransactionState()

    # Reproduce the production ordering: quantitative evidence and the
    # objective FLOP arrive while prior-street ownership still exists.
    tx10 = run_transaction(
        observer,
        state,
        10,
        (
            quantitative(10),
            {
                "frame": 10,
                "type": "FLOP_BOUNDARY_PHYSICAL",
                "board_count": 3,
                "previous_board_count": 0,
            },
        ),
    )

    assert tx10.outcome == "CONTINUE"
    assert observer.hand.street == "PREFLOP"
    assert observer.pending_street_boundaries
    assert "villain" in state.settlement_gate.pending

    before = list(observer.hand.semantic_actions())

    # Production ownership is now exhausted. Critically, do NOT mutate
    # retained["complete_pending"] here. The runtime must recognize this
    # condition itself.
    observer.quantitative_confirmation_pending.pop(
        "villain",
        None,
    )
    observer.quantitative_retry_pending.pop(
        "villain",
        None,
    )

    tx11 = run_transaction(
        observer,
        state,
        11,
        (),
    )

    assert tx11.outcome == "CONTINUE"

    assert "villain" not in state.settlement_gate.pending, (
        "quantitative settlement ownership did not retire"
    )

    after = list(observer.hand.semantic_actions())
    added = after[len(before):]

    # Objective next-street authority may close chronology, but it may
    # not invent a non-zero CALL/FOLD decision.
    assert not any(
        row.get("seat") == "villain"
        and row.get("action") in {
            "CALL",
            "FOLD",
        }
        for row in added
    ), (
        "physical street boundary guessed villain CALL/FOLD"
    )

    assert observer.hand.street == "FLOP", (
        "RED: expired quantitative ownership left retained "
        "physical FLOP deadlocked on PREFLOP"
    )

    assert not observer.pending_street_boundaries, (
        "RED: physical FLOP remained retained after all "
        "prior-street ownership expired"
    )

    print()
    print("NON-ZERO ACTION GUESSED: NO")
    print("OLD STREET DEADLOCKED: NO")
    print(
        "LIVE BOUNDARY COMPLETION AUTHORITY: PASS"
    )


if __name__ == "__main__":
    main()
