"""
Production transaction regression for baseline-equal settlement ownership.

Unchanged trusted stacks must not acquire settlement authority.
Real decreases must retain independent-frame confirmation.
"""

from src.v017.test_same_frame_boundary_quantitative_settlement import (
    PLAYERS,
    run_transaction,
)
from src.v017.frame_hand_observer import FrameHandObserver
import src.v017.run_live_observer as live


def build():
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
        hand_id="baseline-equal-settlement-regression",
    )
    return observer, live.FrameTransactionState()


def observation(frame, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "villain",
        "prior": 50.0,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "candidates": ((value, 1),),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": 50.0 - value,
    }


def main():
    # Scenario 1: unchanged baseline cannot create ownership.
    observer, state = build()

    run_transaction(
        observer, state, 10,
        (observation(10, 50.0),),
    )

    assert "villain" not in state.settlement_gate.pending
    assert "villain" not in state.quantitative_first_seen_frame

    # Scenario 2: a pre-existing stale candidate is retired
    # without immediate re-arming.
    state.settlement_gate.observe(
        observation(11, 50.0),
        phase="PREFLOP",
    )

    assert "villain" in state.settlement_gate.pending

    run_transaction(
        observer, state, 12,
        (observation(12, 50.0),),
    )

    assert "villain" not in state.settlement_gate.pending
    assert "villain" not in state.quantitative_first_seen_frame

    # Scenario 3: genuine stack decrease remains eligible.
    observer, state = build()

    run_transaction(
        observer, state, 20,
        (observation(20, 48.0),),
    )

    assert "villain" in state.settlement_gate.pending

    run_transaction(
        observer, state, 21,
        (observation(21, 48.0),),
    )

    assert "villain" not in state.settlement_gate.pending

    actions = observer.hand.semantic_actions()

    assert any(
        row["seat"] == "villain"
        and row["action"] in {"CALL", "BET", "RAISE"}
        for row in actions
    ), actions

    # Scenario 4: a baseline-equal observation cannot hold a
    # physical FLOP boundary behind false settlement ownership.
    observer, state = build()

    run_transaction(
        observer, state, 30,
        (
            observation(30, 50.0),
            {
                "frame": 30,
                "type": "FLOP_BOUNDARY_PHYSICAL",
                "board_count": 3,
                "previous_board_count": 0,
            },
        ),
    )

    assert "villain" not in state.settlement_gate.pending, (
        "baseline-equal stack rearmed settlement ownership"
    )

    assert observer.hand.street == "FLOP", (
        "baseline-equal settlement blocked physical FLOP"
    )

    assert observer.pending_street_boundaries == [], (
        "FLOP boundary remained retained"
    )

    assert not any(
        row["seat"] == "villain"
        and row["action"] in {"CALL", "FOLD", "BET", "RAISE"}
        for row in observer.hand.semantic_actions()
    ), (
        "boundary fabricated a quantitative action or fold"
    )

    print("BASELINE-EQUAL FLOP BOUNDARY RELEASE: PASS")
    print("BASELINE-EQUAL REARM PREVENTION: PASS")
    print("STALE CANDIDATE RETIREMENT: PASS")
    print("GENUINE STACK SETTLEMENT: PASS")


if __name__ == "__main__":
    main()
