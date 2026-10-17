"""
Regression from live hand 2026-10-16.

Physical sequence:

    frame 10:
        current actor stack region moves
        OCR still equals trusted baseline

    frame 11:
        same-seat bet commitment is independently confirmed
        OCR still equals trusted baseline

    frames 12-14:
        physical stack text remains at trusted baseline

    frame 15:
        ACR finally exposes changed stack

    frame 16:
        changed stack confirms independently

Required behavior:

    a resolved SAME-BASELINE OCR result is not quantitative
    resolution of an already-owned physical action;

    once physical motion/commitment owns bounded measurement work,
    baseline reads must consume retry attempts but must not destroy
    ownership before the configured retry bound;

    the delayed changed value must therefore still be observed and
    enter normal temporal confirmation.

No retry evidence grants poker semantics by itself.
"""

import numpy as np

import src.v017.frame_hand_observer as fho
from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


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


class Resolution:
    def __init__(self, value):
        self.resolved = True
        self.value = float(value)
        self.candidates = (
            (float(value), 1),
        )
        self.confidence = 0.80
        self.votes = 1
        self.mode = "test"


class Motion:
    def __init__(self, wake):
        self.changed_fraction = (
            0.25 if wake else 0.0
        )
        self.mean_diff = (
            20.0 if wake else 0.0
        )
        self.max_diff = (
            200 if wake else 0
        )
        self.wake = bool(wake)


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "villain",
            "hero",
        ],
        small_blind_seat="hero",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {
                "villain": {
                    "x": 0,
                    "y": 0,
                    "width": 20,
                    "height": 20,
                },
            },
        },
        trusted_stacks={
            "villain": 50.0,
            "hero": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[
            "villain",
        ],
        hero_seat="hero",
        hand_id="delayed-stack-text-settlement",
    )

    # Live failure shape:
    # several fully resolved OCR reads remain at the old stack before
    # ACR eventually updates the displayed stack.
    values = {
        10: 50.0,
        11: 50.0,
        12: 50.0,
        13: 50.0,
        14: 50.0,
        15: 48.0,
        16: 48.0,
    }

    current = {"frame": None}

    original_motion = fho.measure_stack_motion
    original_resolve = fho.resolve_fast_stack
    original_board = fho.count_board_cards
    original_hero = fho.hero_cards_visible

    def fake_motion(
        previous_frame,
        frame,
        geometry,
        seat,
    ):
        return Motion(
            current["frame"] == 10
        )

    def fake_resolve(reading, prior):
        return Resolution(
            values[current["frame"]]
        )

    def fake_reader(crop):
        value = values[current["frame"]]

        return {
            "stack_bb": value,
            "confidence": 0.80,
            "votes": 1,
            "candidates": [value],
        }

    def fake_board(frame, geometry):
        return 0

    def fake_hero(frame, geometry):
        return True

    fho.measure_stack_motion = fake_motion
    fho.resolve_fast_stack = fake_resolve
    fho.count_board_cards = fake_board
    fho.hero_cards_visible = fake_hero

    observer.stack_reader = fake_reader

    image = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    observer.previous_frame = image.copy()

    try:
        for frame_id in range(10, 17):
            current["frame"] = frame_id

            # Reproduce the independent commitment evidence that was
            # visible in the real hand while OCR still showed baseline.
            if frame_id >= 11:
                observer.confirmed_bet_regions = {
                    "villain"
                }

            observer.process_frame(
                image.copy(),
                frame_id=frame_id,
                sensor_frame=image.copy(),
                sensor_geometry=observer.geometry,
            )

            if frame_id in (11, 12, 13, 14):
                retry = (
                    observer.quantitative_retry_pending
                    .get("villain")
                )

                assert retry is not None, (
                    "RED: resolved same-baseline OCR destroyed "
                    "physical quantitative ownership at "
                    f"frame {frame_id}"
                )

                assert (
                    observer.trusted_stacks["villain"]
                    == 50.0
                )

                assert (
                    observer.hand.next_actor
                    == "villain"
                )

        # process_frame() owns physical perception and temporal
        # confirmation. Semantic admission is deliberately separate.
        #
        # Therefore trusted_stacks and HandEngine chronology must not
        # be mutated by this perception-only regression.
        assert (
            observer.trusted_stacks["villain"]
            == 50.0
        )

        assert (
            observer.hand.next_actor
            == "villain"
        )

        assert (
            "villain"
            not in observer.quantitative_retry_pending
        )

        assert (
            "villain"
            not in observer.quantitative_confirmation_pending
        )

        print(
            "DELAYED STACK TEXT SETTLEMENT SURVIVES "
            "SAME-BASELINE RETRIES: PASS"
        )
        print(
            "PERCEPTION / SEMANTIC OWNERSHIP REMAINS SEPARATE: PASS"
        )

    finally:
        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero


if __name__ == "__main__":
    main()
