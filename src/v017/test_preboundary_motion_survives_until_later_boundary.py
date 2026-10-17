"""
Regression: stack motion can occur before a later physical street boundary.
The original motion frame must remain available as pre-boundary provenance.
"""

import numpy as np

import src.v017.frame_hand_observer as fho
from src.v017.frame_hand_observer import FrameHandObserver


PLAYERS = [
    {
        "seat": "hero",
        "position": "BB",
        "name": "Hero",
        "stack_bb": 46.43,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "villain",
        "position": "BTN",
        "name": "Villain",
        "stack_bb": 30.0,
        "dealt_in": True,
    },
]


class Motion:
    def __init__(self, wake):
        self.changed_fraction = 0.08 if wake else 0.0
        self.mean_diff = 10.0 if wake else 0.0
        self.max_diff = 210 if wake else 0
        self.wake = bool(wake)


class Resolution:
    def __init__(self, value):
        self.resolved = True
        self.value = float(value)
        self.candidates = ((float(value), 1),)
        self.confidence = 0.80
        self.votes = 1
        self.mode = "test"


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "villain"],
        small_blind_seat="villain",
        big_blind_seat="hero",
        geometry={
            "hole_cards": {},
            "stack_regions": {
                "hero": {
                    "x": 0,
                    "y": 0,
                    "width": 20,
                    "height": 20,
                },
            },
        },
        trusted_stacks={
            "hero": 46.43,
            "villain": 30.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=["hero"],
        hero_seat="hero",
        hand_id="motion-before-later-boundary",
    )

    current = {"frame": None}

    original_motion = fho.measure_stack_motion
    original_resolve = fho.resolve_fast_stack
    original_board = fho.count_board_cards
    original_hero = fho.hero_cards_visible

    def fake_reader(crop):
        return {
            "stack_bb": 46.43,
            "confidence": 0.80,
            "votes": 1,
            "candidates": [46.43],
        }

    def fake_resolve(reading, prior):
        return Resolution(46.43)

    def fake_motion(
        previous_frame,
        frame,
        geometry,
        seat,
    ):
        return Motion(current["frame"] == 4)

    def fake_board(frame, geometry):
        return 3 if current["frame"] >= 7 else 0

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
        for frame_id in range(1, 8):
            current["frame"] = frame_id

            observer.process_frame(
                image.copy(),
                frame_id=frame_id,
                sensor_frame=image.copy(),
                sensor_geometry=observer.geometry,
            )

        provenance = (
            observer.pre_boundary_stack_motion.get("hero")
        )

        print()
        print("provenance =", provenance)
        print(
            "pending boundaries =",
            observer.pending_street_boundaries,
        )
        print()

        assert provenance is not None, (
            "RED: Hero stack motion observed before FLOP "
            "was not preserved when later boundary arrived"
        )

        assert provenance["frame"] == 4, (
            "RED: provenance lost original motion frame"
        )

        assert provenance["boundary_frame"] == 7, (
            "RED: earlier motion was not attached to FLOP"
        )

        assert provenance["street"] == "PREFLOP"

        print(
            "EARLIER STACK MOTION -> LATER BOUNDARY "
            "PROVENANCE: PASS"
        )

    finally:
        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero


if __name__ == "__main__":
    main()
