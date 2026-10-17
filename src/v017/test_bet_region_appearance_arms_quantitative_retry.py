"""
Regression: confirmed physical bet-region appearance must open a
bounded quantitative measurement opportunity for the authoritative
actor even when stack-motion detection does not wake.

Bet-region evidence itself has NO poker-semantic authority.
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


class Motion:
    changed_fraction = 0.0
    mean_diff = 0.0
    max_diff = 0
    wake = False


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
            "bet_regions": {
                "villain": {
                    "x": 30,
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
        hand_id="bet-appearance-quantitative-wake",
    )

    current = {
        "frame": 10,
    }

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
        return Motion()

    def fake_resolve(reading, prior):
        return Resolution(48.0)

    def fake_reader(crop):
        return {
            "stack_bb": 48.0,
            "confidence": 0.80,
            "votes": 1,
            "candidates": [48.0],
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

    # Bypass pixel classification only. Feed the observer the exact
    # confirmed tracker result that observe_bet_regions() normally
    # receives after its debounce period.
    original_observe_bet_regions = (
        observer.observe_bet_regions
    )

    def confirmed_appearance(frame):
        observer.confirmed_bet_regions = {
            "villain",
        }

        return {
            "villain": {
                "occupied": True,
                "appeared": True,
                "cleared": False,
                "changed": True,
                "occupied_duration_ms": 150.0,
            },
        }

    observer.observe_bet_regions = (
        confirmed_appearance
    )

    try:
        result = observer.process_frame(
            image.copy(),
            frame_id=10,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert observer.hand.next_actor == "villain"

        # Stack motion was deliberately absent.
        # Therefore the confirmed commitment appearance itself must
        # have opened bounded quantitative ownership.
        # The confirmed appearance must have opened measurement
        # ownership. Because this frame immediately resolved a changed
        # stack value, retry ownership is correctly consumed into
        # temporal confirmation ownership during the same transaction.
        assert (
            "villain"
            not in observer.quantitative_retry_pending
        )

        confirmation = (
            observer.quantitative_confirmation_pending
            .get("villain")
        )

        assert confirmation is not None, (
            "confirmed bet-region appearance reached OCR but "
            "did not transfer into temporal confirmation"
        )

        assert confirmation["value"] == 48.0
        assert confirmation["first_frame"] == 10

        quantitative = [
            event
            for event in result.events
            if (
                event.get("type")
                == "STACK_QUANTITATIVE_OBSERVATION"
                and event.get("seat")
                == "villain"
            )
        ]

        assert quantitative, (
            "RED: confirmed bet-region appearance did not "
            "schedule targeted stack OCR"
        )

        # First quantitative observation still has no poker-semantic
        # authority. Independent temporal confirmation is mandatory.
        assert observer.hand.next_actor == "villain"

        semantic = [
            action
            for action in observer.hand.actions
            if action.seat == "villain"
        ]

        assert semantic == [], semantic

        print(
            "BET REGION APPEARANCE -> "
            "QUANTITATIVE MEASUREMENT: PASS"
        )

        print(
            "FIRST STACK OBSERVATION -> "
            "TEMPORAL CONFIRMATION OWNERSHIP: PASS"
        )

        # Frame 11 has no new bet-region appearance and no stack-motion
        # wake. Confirmation ownership alone must schedule the second
        # independent 48 BB observation.
        current["frame"] = 11

        def no_transition(frame):
            observer.confirmed_bet_regions = {
                "villain",
            }

            return {
                "villain": {
                    "occupied": True,
                    "appeared": False,
                    "cleared": False,
                    "changed": False,
                    "occupied_duration_ms": 300.0,
                },
            }

        observer.observe_bet_regions = no_transition

        result11 = observer.process_frame(
            image.copy(),
            frame_id=11,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert (
            "villain"
            not in observer.quantitative_confirmation_pending
        )

        q11 = [
            event
            for event in result11.events
            if (
                event.get("type")
                == "STACK_QUANTITATIVE_OBSERVATION"
                and event.get("seat")
                == "villain"
            )
        ]

        assert q11, (
            "temporal confirmation ownership did not schedule "
            "the second quantitative observation"
        )

        # process_frame() remains perception-only here. No direct
        # poker action may have been manufactured from chip occupancy.
        assert observer.hand.next_actor == "villain"

        semantic = [
            action
            for action in observer.hand.actions
            if action.seat == "villain"
        ]

        assert semantic == [], semantic

        print(
            "BET REGION APPEARANCE -> DELAYED "
            "QUANTITATIVE CONFIRMATION: PASS"
        )

        print(
            "BET REGION APPEARANCE HAS "
            "NO DIRECT SEMANTIC AUTHORITY: PASS"
        )

    finally:
        observer.observe_bet_regions = (
            original_observe_bet_regions
        )

        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero


if __name__ == "__main__":
    main()
