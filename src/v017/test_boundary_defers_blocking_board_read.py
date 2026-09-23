"""
V0.17 same-frame boundary deferral regression.

Physical perception may legitimately emit:

    1. STREET_BOUNDARY_PHYSICAL
    2. STACK_QUANTITATIVE_OBSERVATION

in raw detector order.

Raw physical event order must not give an expensive street-boundary
board-identity read priority over an already-confirmable quantitative
observation from the same captured frame.

Required transaction order:

    quantitative settlement/admission
    publication of resulting canonical action
    board identity read
    street-boundary admission/reconciliation

This test does not weaken two-frame settlement authority.
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
        "seat": "raiser",
        "position": "BTN",
        "name": "Raiser",
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
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]



def quantitative(
    frame,
    value,
):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "bb",
        "prior": 50.0,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "candidates": (
            (value, 1),
        ),
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": (
            50.0 - value
        ),
    }


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "raiser",
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "raiser": 50.0,
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id=(
            "boundary-defers-blocking-board"
        ),
    )

    hand = observer.hand

    # Reproduce the production boundary state:
    #
    # BTN raises to 2 BB.
    # SB calls the remaining 1.5 BB.
    # BB has posted 1 BB and is last to act facing 2 BB.
    #
    # Therefore a later independently confirmed 1 BB physical
    # decrease from BB must semantically become CALL.
    assert (
        hand.observe_stack_commitment(
            "raiser",
            2.0,
        )
        == "RAISE"
    )

    assert (
        hand.observe_stack_commitment(
            "hero",
            1.5,
        )
        == "CALL"
    )

    assert hand.street == "PREFLOP"
    assert hand.next_actor == "bb"

    assert abs(
        hand.current_price_bb - 2.0
    ) < 0.001

    assert abs(
        hand.players[
            "bb"
        ].street_commitment_bb
        - 1.0
    ) < 0.001

    # Physical authority still references BB's pre-call stack.
    # No semantic BB action has occurred.
    observer.trusted_stacks[
        "bb"
    ] = 50.0

    return observer



def main():
    observer = build_observer()
    state = live.FrameTransactionState()

    # --------------------------------------------------------
    # FRAME 20
    #
    # Establish first native quantitative observation.
    # It must NOT settle from one frame.
    # --------------------------------------------------------

    first = quantitative(
        20,
        49.0,
    )

    settled = state.settlement_gate.observe(
        first,
        phase=observer.hand.street,
        has_commitment_evidence=True,
    )

    assert settled is None
    assert "bb" in state.settlement_gate.pending
    assert observer.hand.next_actor == "bb"

    before_actions = len(
        observer.hand.actions
    )

    # --------------------------------------------------------
    # FRAME 21
    #
    # Raw physical order intentionally reproduces production:
    #
    #   boundary first
    #   quantitative confirmation second
    # --------------------------------------------------------

    events = (
        {
            "frame": 21,
            "type":
                "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 1,
        },
        quantitative(
            21,
            49.0,
        ),
    )

    original_process_frame = (
        observer.process_frame
    )
    original_board_reader = (
        live.read_board_identity
    )
    original_publish_new = (
        live.publish_new
    )

    execution = []

    def fake_process_frame(
        image,
        frame_id,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        assert frame_id == 21

        return FrameObservationResult(
            frame_id=frame_id,
            events=events,
            changed=False,
            text=None,
        )

    def fake_board_reader(
        frame_path,
        expected_count,
    ):
        assert expected_count == 3

        execution.append(
            (
                "board_read",
                len(observer.hand.actions),
                observer.hand.street,
            )
        )

        return [
            "Jd",
            "9s",
            "Tc",
        ]

    def recording_publish_new(
        observed,
        before_count,
    ):
        rows = original_publish_new(
            observed,
            before_count,
        )

        if rows:
            execution.append(
                (
                    "publication",
                    len(observed.hand.actions),
                    observed.hand.street,
                )
            )

        return rows

    observer.process_frame = (
        fake_process_frame
    )

    live.read_board_identity = (
        fake_board_reader
    )

    live.publish_new = (
        recording_publish_new
    )

    try:
        image = np.zeros(
            (
                696,
                934,
                3,
            ),
            dtype=np.uint8,
        )

        tx = live.process_frame_transaction(
            observer,
            image,
            Path(
                "/tmp/"
                "boundary_deferral_frame_21.png"
            ),
            21,
            state,
        )

    finally:
        observer.process_frame = (
            original_process_frame
        )

        live.read_board_identity = (
            original_board_reader
        )

        live.publish_new = (
            original_publish_new
        )

    print(
        "raw_event_order =",
        [
            event["type"]
            for event in events
        ],
    )

    print(
        "execution =",
        execution,
    )

    print(
        "actions_before =",
        before_actions,
    )

    print(
        "actions_after =",
        len(observer.hand.actions),
    )

    print(
        "street_after =",
        observer.hand.street,
    )

    assert tx.outcome == "CONTINUE"

    # One new semantic action must exist: BB CALL.
    new_actions = (
        observer.hand
        .semantic_actions()[
            before_actions:
        ]
    )

    print(
        "new_actions =",
        new_actions,
    )

    assert len(new_actions) == 1

    assert (
        new_actions[0]["seat"]
        == "bb"
    )

    assert (
        new_actions[0]["action"]
        == "CALL"
    )

    # --------------------------------------------------------
    # RED CONTRACT
    #
    # At the instant board identity begins, the quantitative
    # action must already be canonical.
    # --------------------------------------------------------

    board_rows = [
        row
        for row in execution
        if row[0] == "board_read"
    ]

    assert len(board_rows) == 1

    board_read = board_rows[0]

    print(
        "actions_when_board_read_started =",
        board_read[1],
    )

    assert (
        board_read[1]
        == before_actions + 1
    ), (
        "blocking board read started before "
        "same-frame quantitative action was admitted",
        execution,
    )

    # The resulting action must also have reached the live
    # publication boundary before board identity starts.
    publication_indices = [
        index
        for index, row in enumerate(
            execution
        )
        if row[0] == "publication"
    ]

    board_index = next(
        index
        for index, row in enumerate(
            execution
        )
        if row[0] == "board_read"
    )

    assert publication_indices, execution

    assert (
        publication_indices[0]
        < board_index
    ), (
        "canonical action was not published "
        "before blocking board identity",
        execution,
    )

    # Boundary still admits normally afterward.
    assert observer.hand.street == "FLOP"

    assert observer.hand.board == [
        "Jd",
        "9s",
        "Tc",
    ]

    print()
    print(
        "QUANTITATIVE SETTLEMENT BEFORE BOARD READ: PASS"
    )
    print(
        "ACTION PUBLICATION BEFORE BOARD READ: PASS"
    )
    print(
        "BOUNDARY ADMISSION AFTER BOARD READ: PASS"
    )
    print(
        "RAW EVENT ORDER OWNS SEMANTICS: NO"
    )
    print()
    print(
        "V0.17 BOUNDARY DEFERRAL: PASS"
    )


if __name__ == "__main__":
    main()
