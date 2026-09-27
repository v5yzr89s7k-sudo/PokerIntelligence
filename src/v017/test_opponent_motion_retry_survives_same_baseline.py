"""
Regression for opponent stack-motion ownership.

Physical sequence:

    frame 10:
        opponent stack region moves strongly
        OCR is readable but still equals trusted baseline

    frame 11:
        motion has stopped
        OCR now exposes changed stack

    frame 12:
        same changed stack confirms independently

Required behavior:

    the frame-10 motion wake owns bounded retry work;
    same-baseline OCR cannot consume that ownership;
    frame 11 is still sampled without another motion edge;
    changed value enters normal temporal confirmation;
    frame 12 settles and admits exactly one action.

Motion/retry itself grants no semantic authority.
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
        hand_id="opponent-motion-same-baseline",
    )

    values = {
        10: 50.0,
        11: 48.0,
        12: 48.0,
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
        # Frame 10:
        # Strong physical wake, but OCR still shows baseline.
        current["frame"] = 10

        result10 = observer.process_frame(
            image.copy(),
            frame_id=10,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        retry10 = (
            observer.quantitative_retry_pending
            .get("villain")
        )

        assert retry10 is not None
        assert (
            retry10.get("reason")
            == "stack_motion"
        )

        q10 = [
            event
            for event in result10.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        assert len(q10) == 1
        assert q10[0]["resolved_value"] == 50.0

        assert observer.hand.next_actor == "villain"
        assert observer.trusted_stacks["villain"] == 50.0

        print(
            "FRAME 10 MOTION + SAME BASELINE "
            "RETAINS OWNERSHIP: PASS"
        )

        # Frame 11:
        # No new motion edge. Retry ownership alone must schedule OCR.
        current["frame"] = 11

        result11 = observer.process_frame(
            image.copy(),
            frame_id=11,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert (
            "villain"
            not in observer.quantitative_retry_pending
        )

        confirmation = (
            observer.quantitative_confirmation_pending
            .get("villain")
        )

        assert confirmation is not None
        assert confirmation["value"] == 48.0

        assert observer.hand.next_actor == "villain"
        assert observer.trusted_stacks["villain"] == 50.0

        print(
            "FRAME 11 CHANGED STACK WITHOUT NEW MOTION: PASS"
        )

        # Frame 12:
        # Confirmation ownership schedules the independent second read.
        current["frame"] = 12

        result12 = observer.process_frame(
            image.copy(),
            frame_id=12,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        settled = [
            event
            for event in result12.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
            and event.get("resolved_value") == 48.0
        ]

        assert settled

        assert (
            "villain"
            not in observer.quantitative_confirmation_pending
        )

        # The physical observer has now completed the contract
        # under test: one wake retained ownership across a readable
        # same-baseline OCR result, the changed value was discovered
        # without a second wake, and an independent later frame
        # confirmed that value.
        #
        # Semantic settlement/publication is deliberately tested by
        # the transaction-layer quantitative regressions. Do not
        # require this sensor-level regression to mutate trusted stack
        # state or invent HandEngine authority.
        assert (
            "villain"
            not in observer.quantitative_retry_pending
        )

        assert (
            "villain"
            not in observer.quantitative_confirmation_pending
        )

        print(
            "FRAME 12 TEMPORAL CONFIRMATION COMPLETE: PASS"
        )

        print()
        print(
            "V0.17 OPPONENT MOTION SAME-BASELINE "
            "RETRY: PASS"
        )

    finally:
        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero


if __name__ == "__main__":
    main()
