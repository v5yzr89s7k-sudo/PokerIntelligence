
"""A retained confirmed settlement cannot be confirmed twice."""

from contextlib import redirect_stdout
from io import StringIO
import re

import cv2

from src.v017.test_sept17_allin_production_path import (
    CAPTURES,
    ControlledClock,
    make_observer,
)
from src.v017.run_live_observer import (
    FrameTransactionState,
    process_frame_transaction,
)


def main():
    assert len(CAPTURES) > 31

    clock = ControlledClock()
    observer = make_observer(clock)
    state = FrameTransactionState()

    output = StringIO()

    try:
        with redirect_stdout(output):
            for frame_id in range(24, 32):
                image = cv2.imread(
                    str(CAPTURES[frame_id])
                )
                assert image is not None

                if frame_id > 24:
                    clock.advance(0.25)

                process_frame_transaction(
                    observer,
                    image,
                    CAPTURES[frame_id],
                    frame_id,
                    state,
                )
    finally:
        state.board_identity_reader.close()

    lines = output.getvalue().splitlines()

    settlements = [
        line for line in lines
        if line.startswith("[STACK_SETTLED]")
        and "seat=seat_mid_right" in line
        and "prior=22.94" in line
        and "value=0.0" in line
    ]

    retained = [
        row
        for row in observer.pending_quantitative_evidence
        if row.get("seat") == "seat_mid_right"
        and row.get("frame") == 26
        and row.get("settlement_confirmed") is True
        and abs(
            float(row.get("resolved_value", -1))
        ) <= 0.01
    ]

    print("settlement_count=", len(settlements))
    print("retained_frame26=", len(retained))
    print("trusted_stack=", observer.trusted_stacks["seat_mid_right"])
    print("next_actor=", observer.hand.next_actor)

    assert len(settlements) == 1, (
        "RED: DUPLICATE PHYSICAL SETTLEMENT",
        settlements,
    )

    assert len(retained) == 1, (
        "ORIGINAL CONFIRMED EVIDENCE LOST",
        retained,
    )

    assert observer.hand.next_actor == "seat_upper_right"
    assert observer.trusted_stacks["seat_mid_right"] == 22.94

    assert not [
        action
        for action in observer.hand.semantic_actions()
        if action.get("seat") == "seat_mid_right"
        and action.get("action") in (
            "CALL", "RAISE", "BET", "ALL_IN"
        )
    ]

    print("RETAINED SETTLEMENT OWNERSHIP: PASS")


if __name__ == "__main__":
    main()
