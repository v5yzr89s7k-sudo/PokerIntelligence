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
        hand_id="opponent-settlement-before-flop",
    )

    state = live.FrameTransactionState()

    assert observer.hand.next_actor == "villain"

    before = len(observer.hand.semantic_actions())

    tx10 = run_transaction(
        observer,
        state,
        10,
        (quantitative(10),),
    )

    assert tx10.outcome == "CONTINUE"
    assert observer.hand.next_actor == "villain"
    assert len(observer.hand.semantic_actions()) == before
    assert "villain" in state.settlement_gate.pending

    tx11 = run_transaction(
        observer,
        state,
        11,
        (quantitative(11),),
    )

    assert tx11.outcome == "CONTINUE"
    assert "villain" not in state.settlement_gate.pending

    actions = observer.hand.semantic_actions()
    new = actions[before:]

    assert len(new) == 1
    assert new[0]["seat"] == "villain"

    print(
        "OPPONENT TWO-FRAME TRANSACTION "
        "SETTLEMENT: PASS"
    )

    # Hero now completes preflop objectively.
    folded = observer.admit_card_disappearance(
        "hero",
        frame_id=11,
        physical_type="HERO_CARDS_DISAPPEARED_PHYSICAL",
    )

    assert folded
    assert observer.hand.next_actor is None

    boundary = {
        "frame": 12,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
        "previous_board_count": 0,
    }

    admitted = observer.admit_street_boundary(
        boundary,
        action_order=["villain"],
        board=["As", "Kd", "7c"],
        complete_pending=True,
    )

    assert admitted
    assert observer.hand.street == "FLOP"
    assert observer.hand.board == [
        "As",
        "Kd",
        "7c",
    ]

    preflop = [
        row
        for row in observer.hand.semantic_actions()
        if row.get("street") == "PREFLOP"
    ]

    villain = [
        row
        for row in preflop
        if row.get("seat") == "villain"
    ]

    assert len(villain) == 1

    unknown = [
        event
        for event in observer.events
        if event.get("type")
        == "STREET_BOUNDARY_UNKNOWN_COMPLETION"
        and event.get("seat") == "villain"
    ]

    assert unknown == []

    print(
        "FLOP BOUNDARY PRESERVED OPPONENT "
        "PREFLOP ACTION: PASS"
    )

    print(
        "V0.17 OPPONENT SETTLEMENT "
        "BEFORE FLOP BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
