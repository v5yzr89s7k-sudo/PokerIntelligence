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
        image = np.zeros((696, 934, 3), dtype=np.uint8)

        return live.process_frame_transaction(
            observer,
            image,
            Path(f"/tmp/opponent_boundary_{frame_id}.png"),
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
        hand_id="same-frame-boundary-quantitative",
    )

    state = live.FrameTransactionState()

    before = len(observer.hand.semantic_actions())

    # FRAME 10:
    # First quantitative observation and physical FLOP
    # boundary arrive together.
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

    # Boundary must NOT overtake the pending quantitative
    # candidate.
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "villain"
    assert "villain" in state.settlement_gate.pending
    assert observer.pending_street_boundaries

    unknown = [
        event
        for event in observer.events
        if event.get("type")
        == "STREET_BOUNDARY_UNKNOWN_COMPLETION"
        and event.get("seat") == "villain"
    ]

    assert unknown == []

    print(
        "FRAME 10 BOUNDARY RETAINED BEHIND "
        "QUANTITATIVE OWNERSHIP: PASS"
    )

    # FRAME 11:
    # Independent physical confirmation settles Villain.
    tx11 = run_transaction(
        observer,
        state,
        11,
        (quantitative(11),),
    )

    assert tx11.outcome == "CONTINUE"

    actions = observer.hand.semantic_actions()
    new = actions[before:]

    villain = [
        row
        for row in new
        if row.get("seat") == "villain"
        and row.get("street") == "PREFLOP"
    ]

    assert len(villain) == 1
    assert "villain" not in state.settlement_gate.pending

    print(
        "FRAME 11 QUANTITATIVE ACTION SETTLED "
        "ON PREFLOP: PASS"
    )

    # The retained FLOP may still wait for Hero's remaining
    # objective preflop completion.
    folded = observer.admit_card_disappearance(
        "hero",
        frame_id=11,
        physical_type="HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    assert folded

    observer.reconcile_pending_street_boundaries()

    assert observer.hand.street == "FLOP"
    assert observer.pending_street_boundaries == []

    unknown = [
        event
        for event in observer.events
        if event.get("type")
        == "STREET_BOUNDARY_UNKNOWN_COMPLETION"
        and event.get("seat") == "villain"
    ]

    assert unknown == []

    print(
        "RETAINED FLOP ACTIVATED AFTER PREFLOP "
        "CHRONOLOGY CLOSED: PASS"
    )

    print(
        "V0.17 SAME-FRAME BOUNDARY / "
        "QUANTITATIVE SETTLEMENT: PASS"
    )


if __name__ == "__main__":
    main()
