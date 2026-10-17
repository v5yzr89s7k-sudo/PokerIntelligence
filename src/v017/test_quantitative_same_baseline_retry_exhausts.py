"""
Regression for bounded same-baseline quantitative retry ownership.

A physical stack-motion wake may legitimately precede ACR's displayed
stack update. Same-baseline OCR must therefore retain retry ownership.

But if the displayed stack never changes, ownership must terminate at
the configured quantitative_retry_max_attempts bound.
"""

import numpy as np

import src.v017.frame_hand_observer as fho
from src.v017.frame_hand_observer import FrameHandObserver


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
        self.candidates = ((float(value), 1),)
        self.confidence = 0.80
        self.votes = 1
        self.mode = "test"


class Motion:
    def __init__(self, wake):
        self.changed_fraction = 0.25 if wake else 0.0
        self.mean_diff = 20.0 if wake else 0.0
        self.max_diff = 200 if wake else 0
        self.wake = bool(wake)


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["villain", "hero"],
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
        quantitative_seats=["villain"],
        hero_seat="hero",
        hand_id="same-baseline-retry-exhaustion",
    )

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
        return Motion(current["frame"] == 10)

    def fake_resolve(reading, prior):
        return Resolution(50.0)

    def fake_reader(crop):
        return {
            "stack_bb": 50.0,
            "confidence": 0.80,
            "votes": 1,
            "candidates": [50.0],
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
        max_attempts = (
            observer.quantitative_retry_max_attempts
        )

        # Frame 10 owns attempt 1. Continue long enough to reach the
        # configured bound while OCR remains permanently unchanged.
        final_frame = 10 + max_attempts - 1

        for frame_id in range(10, final_frame + 1):
            current["frame"] = frame_id

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

            if frame_id < final_frame:
                retry = (
                    observer.quantitative_retry_pending
                    .get("villain")
                )

                assert retry is not None, (
                    "same-baseline retry ownership terminated "
                    f"before configured bound at frame {frame_id}"
                )

        assert (
            "villain"
            not in observer.quantitative_retry_pending
        ), (
            "same-baseline retry ownership survived beyond "
            "configured maximum attempts"
        )

        assert (
            "villain"
            not in observer.quantitative_confirmation_pending
        )

        assert (
            observer.trusted_stacks["villain"]
            == 50.0
        )

        assert (
            observer.hand.next_actor
            == "villain"
        )

        print(
            "SAME-BASELINE RETRY EXHAUSTS AT "
            f"{max_attempts} ATTEMPTS: PASS"
        )
        print(
            "EXHAUSTION CREATES NO SEMANTIC ACTION: PASS"
        )

    finally:
        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero


if __name__ == "__main__":
    main()
