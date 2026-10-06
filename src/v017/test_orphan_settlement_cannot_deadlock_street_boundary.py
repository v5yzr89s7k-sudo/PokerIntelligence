"""
Regression for an orphan StackSettlementGate candidate retaining a
physical next-street boundary forever.

Contract:

* a first pre-boundary quantitative observation may legitimately arm
  temporal settlement ownership;
* the physical FLOP must initially wait for that ownership;
* once the observer's bounded quantitative confirmation ownership is
  gone, an unconfirmed gate candidate must no longer retain PREFLOP
  forever;
* legitimate next-frame confirmation remains covered independently by
  test_same_frame_boundary_quantitative_settlement.
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


def run_transaction(
    observer,
    state,
    frame_id,
    events,
):
    original = observer.process_frame

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        return frame_result(
            frame_id,
            events,
        )

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
                f"/tmp/orphan_settlement_{frame_id}.png"
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
        hand_id="orphan-settlement-boundary",
    )

    state = live.FrameTransactionState()

    # First physical quantitative observation and FLOP arrive together.
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
    assert "villain" in state.settlement_gate.pending
    assert observer.pending_street_boundaries

    print(
        "INITIAL PRE-BOUNDARY SETTLEMENT OWNERSHIP: PASS"
    )

    # Model the production condition observed live:
    # FrameHandObserver's bounded confirmation/retry owners have
    # exhausted without producing independent confirmation.
    observer.quantitative_confirmation_pending.pop(
        "villain",
        None,
    )
    observer.quantitative_retry_pending.pop(
        "villain",
        None,
    )

    # No new quantitative evidence arrives. The orphan gate candidate
    # must not retain the objective FLOP forever.
    tx11 = run_transaction(
        observer,
        state,
        11,
        (),
    )

    assert tx11.outcome == "CONTINUE"

    assert "villain" not in state.settlement_gate.pending, (
        "RED: StackSettlementGate candidate survived after all "
        "physical confirmation ownership expired"
    )

    # Once quantitative ownership is gone, the objective FLOP
    # boundary may use its normal completion authority for unresolved
    # predecessor chronology.
    for retained in observer.pending_street_boundaries:
        retained["complete_pending"] = True

    observer.reconcile_pending_street_boundaries()

    assert observer.hand.street == "FLOP", (
        "RED: orphan settlement candidate deadlocked retained FLOP"
    )

    print(
        "ORPHAN SETTLEMENT RETIRED: PASS"
    )
    print(
        "RETAINED FLOP RELEASED: PASS"
    )
    print(
        "V0.17 ORPHAN SETTLEMENT CANNOT "
        "DEADLOCK STREET BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
