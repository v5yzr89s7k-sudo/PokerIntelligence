
"""September 17 native production transaction regression."""

from contextlib import redirect_stdout
from io import StringIO

import cv2

from src.v017.test_sept17_utg_hj_product_chronology import (
    CAPTURES,
    ControlledClock,
    build,
)
from src.v017.run_live_observer import (
    FrameTransactionState,
    process_frame_transaction,
)


def run_once():
    assert len(CAPTURES) > 31

    clock = ControlledClock()
    observer = build(clock)
    state = FrameTransactionState()
    output = StringIO()

    try:
        with redirect_stdout(output):
            for frame_id in range(32):
                if frame_id:
                    clock.advance(0.25)

                image = cv2.imread(str(CAPTURES[frame_id]))
                assert image is not None

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
    actions = observer.hand.semantic_actions()

    expected = [
        ("seat_mid_left", "POST_SMALL_BLIND"),
        ("seat_top", "POST_BIG_BLIND"),
        ("seat_upper_right", "RAISE"),
        ("seat_mid_right", "RAISE"),
        ("seat_lower_right", "FOLD"),
    ]

    actual = [
        (row["seat"], row["action"])
        for row in actions
    ]

    assert actual == expected, actual

    settlements = [
        line for line in lines
        if line.startswith("[STACK_SETTLED]")
    ]

    assert len([
        line for line in settlements
        if "seat=seat_upper_right" in line
        and "prior=92.75" in line
        and "value=86.75" in line
    ]) == 1

    assert len([
        line for line in settlements
        if "seat=seat_mid_right" in line
        and "prior=22.94" in line
        and "value=0.0" in line
    ]) == 1

    assert observer.trusted_stacks["seat_upper_right"] == 86.75
    assert observer.trusted_stacks["seat_mid_right"] == 0.0

    assert state.settlement_gate.pending == {}

    assert observer.hand.next_actor == "hero"

    assert any(
        "[CARD_DISAPPEARANCE_RECONCILED]" in line
        and "seat=seat_lower_right" in line
        and "action=FOLD" in line
        for line in lines
    )

    print("SEPT17 PRODUCTION TRANSACTION: PASS")

    return (
        tuple(
            (
                row["seat"],
                row["action"],
                row.get("amount_bb"),
                row.get("raise_to_bb"),
            )
            for row in actions
        ),
        tuple(settlements),
    )


def main():
    first = run_once()
    second = run_once()
    third = run_once()

    assert first == second == third

    print("SEPT17 PRODUCTION DETERMINISM: 3/3 PASS")


if __name__ == "__main__":
    main()
