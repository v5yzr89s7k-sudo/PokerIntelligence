"""
Behavioral regression for the live timing hole:

    frame 20:
        Hero buttons disappear
        OCR is readable but still equals old trusted stack

    frame 21:
        OCR still equals old trusted stack

    frame 22:
        legal changed Hero stack finally appears

    frame 23:
        independent later-frame confirmation

    frame 24:
        physical FLOP boundary

Required behavior:

    same-baseline reads do not consume Hero-completion ownership;
    changed stack enters normal confirmation/settlement;
    Hero semantic action completes before FLOP;
    FLOP then advances normally.

The test uses real FrameHandObserver physical processing for the
quantitative retry lifecycle and real process_frame_transaction for
semantic settlement.
"""

from pathlib import Path
from threading import Event

import numpy as np

import src.v017.frame_hand_observer as fho
import src.v017.run_live_observer as live

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)


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


class Resolution:
    def __init__(self, value):
        self.resolved = True
        self.value = float(value)
        self.candidates = (
            (float(value), 1),
        )
        self.confidence = 0.80
        self.votes = 1
        self.mode = "native_green_fast"


class Motion:
    changed_fraction = 0.0
    mean_diff = 0.0
    max_diff = 0
    wake = False


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
            "raiser": 50.0,
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[
            "hero",
        ],
        hero_seat="hero",
        hand_id="hero-delayed-stack-transition",
    )

    hand = observer.hand

    assert (
        hand.observe_stack_commitment(
            "raiser",
            3.0,
        )
        == "RAISE"
    )

    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 3.0

    return observer


def main():
    observer = build_observer()
    state = live.FrameTransactionState()

    original_motion = fho.measure_stack_motion
    original_resolve = fho.resolve_fast_stack
    original_buttons = fho.action_buttons_visible
    original_hero_cards = fho.hero_cards_visible
    original_board_count = fho.count_board_cards
    original_board_reader = live.read_board_identity

    values = {
        20: 50.0,
        21: 50.0,
        22: 47.5,
        23: 47.5,
    }

    current_frame = {
        "id": None,
    }

    def fake_motion(
        previous_frame,
        frame,
        geometry,
        seat,
    ):
        return Motion()

    def fake_resolve(
        reading,
        prior,
    ):
        frame_id = current_frame["id"]

        assert frame_id in values

        return Resolution(
            values[frame_id]
        )

    def fake_stack_reader(crop):
        frame_id = current_frame["id"]

        assert frame_id in values

        value = float(
            values[frame_id]
        )

        return {
            "stack_bb": value,
            "stack_text":
                f"{value:g} BB",
            "confidence": 0.80,
            "votes": 1,
            "mode":
                "native_green_fast",
            "raw": [],
        }

    def fake_buttons(
        frame,
        geometry,
    ):
        # Frame 19 establishes visible baseline.
        # Frame 20 is the physical disappearance edge.
        return (
            current_frame["id"]
            == 19
        )

    def fake_hero_cards(
        frame,
        geometry,
    ):
        return True

    def fake_board_count(
        frame,
        geometry,
    ):
        return 0

    board_release = Event()

    def board_reader(
        frame_path,
        expected_count,
    ):
        assert expected_count == 3

        if not board_release.wait(
            timeout=5.0
        ):
            raise RuntimeError(
                "board release timeout"
            )

        return [
            "Jd",
            "9s",
            "Tc",
        ]

    fho.measure_stack_motion = fake_motion
    fho.resolve_fast_stack = fake_resolve
    fho.action_buttons_visible = fake_buttons
    fho.hero_cards_visible = fake_hero_cards
    fho.count_board_cards = fake_board_count
    live.read_board_identity = board_reader

    observer.stack_reader = fake_stack_reader

    image = np.zeros(
        (
            696,
            934,
            3,
        ),
        dtype=np.uint8,
    )

    try:
        # Establish physical baselines.
        observer.previous_frame = image.copy()

        current_frame["id"] = 19
        observer.previous_action_buttons_visible = True
        observer.previous_hero_cards_visible = True

        before = len(
            observer.hand.semantic_actions()
        )

        # ----------------------------------------------------
        # FRAME 20
        # Button disappearance arms Hero-completion retry.
        # OCR still sees trusted baseline.
        # ----------------------------------------------------

        current_frame["id"] = 20

        result20 = observer.process_frame(
            image.copy(),
            frame_id=20,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert any(
            event.get("type")
            == "HERO_ACTION_BUTTONS_DISAPPEARED"
            for event in result20.events
        )

        retry20 = (
            observer.quantitative_retry_pending
            .get("hero")
        )

        assert retry20 is not None
        assert (
            retry20.get("reason")
            == "hero_action_completion"
        )
        assert retry20.get("attempts") == 1

        quantitative20 = [
            event
            for event in result20.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        assert len(quantitative20) == 1

        assert (
            quantitative20[0]["resolved_value"]
            == 50.0
        )

        assert (
            quantitative20[0]["prior"]
            == 50.0
        )

        assert (
            quantitative20[0].get(
                "physical_delta_bb",
                0.0,
            )
            == 0.0
        )

        # Same-baseline physical evidence carries no semantic
        # action authority. Hero remains unresolved while bounded
        # completion retry ownership survives.
        assert (
            len(observer.hand.semantic_actions())
            == before
        )

        assert observer.hand.next_actor == "hero"

        assert (
            observer.trusted_stacks["hero"]
            == 50.0
        )

        print(
            "FRAME 20 SAME BASELINE "
            "RETAINS HERO OWNERSHIP: PASS"
        )

        # ----------------------------------------------------
        # FRAME 21
        # Still baseline. Ownership must remain.
        # ----------------------------------------------------

        current_frame["id"] = 21

        result21 = observer.process_frame(
            image.copy(),
            frame_id=21,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        retry21 = (
            observer.quantitative_retry_pending
            .get("hero")
        )

        assert retry21 is not None
        assert retry21.get("attempts") == 2

        quantitative21 = [
            event
            for event in result21.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        assert len(quantitative21) == 1

        assert (
            quantitative21[0]["resolved_value"]
            == 50.0
        )

        assert (
            quantitative21[0]["prior"]
            == 50.0
        )

        assert (
            quantitative21[0].get(
                "physical_delta_bb",
                0.0,
            )
            == 0.0
        )

        assert (
            len(observer.hand.semantic_actions())
            == before
        )

        assert observer.hand.next_actor == "hero"

        assert (
            observer.trusted_stacks["hero"]
            == 50.0
        )

        print(
            "FRAME 21 SAME BASELINE "
            "STILL RETAINS HERO OWNERSHIP: PASS"
        )

        # ----------------------------------------------------
        # FRAME 22
        # Changed legal stack finally appears.
        # This must retire retry ownership and emit first
        # quantitative evidence.
        # ----------------------------------------------------

        current_frame["id"] = 22

        result22 = observer.process_frame(
            image.copy(),
            frame_id=22,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert (
            "hero"
            not in observer.quantitative_retry_pending
        )

        quantitative22 = [
            event
            for event in result22.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        assert len(quantitative22) == 1
        assert (
            quantitative22[0]["resolved_value"]
            == 47.5
        )

        # Feed the real transaction owner exactly the physical
        # evidence produced by the real observer.
        original_process = observer.process_frame

        def tx22_process(
            frame,
            frame_id=None,
            sensor_frame=None,
            sensor_geometry=None,
        ):
            assert frame_id == 22
            return FrameObservationResult(
                frame_id=22,
                events=tuple(
                    quantitative22
                ),
                changed=False,
                text=None,
            )

        observer.process_frame = tx22_process

        try:
            live.process_frame_transaction(
                observer,
                image.copy(),
                Path(
                    "/tmp/"
                    "hero_delayed_stack_22.png"
                ),
                22,
                state,
            )
        finally:
            observer.process_frame = original_process

        assert (
            state.settlement_gate.pending
            .get("hero")
            is not None
        )

        assert observer.hand.next_actor == "hero"

        print(
            "FRAME 22 CHANGED STACK "
            "ENTERS SETTLEMENT: PASS"
        )

        # ----------------------------------------------------
        # FRAME 23
        # Confirmation ownership must force another read even
        # without motion and settle the Hero action.
        # ----------------------------------------------------

        current_frame["id"] = 23

        result23 = observer.process_frame(
            image.copy(),
            frame_id=23,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        quantitative23 = [
            event
            for event in result23.events
            if event.get("type")
            == "STACK_QUANTITATIVE_OBSERVATION"
        ]

        assert len(quantitative23) == 1
        assert (
            quantitative23[0]["resolved_value"]
            == 47.5
        )

        original_process = observer.process_frame

        def tx23_process(
            frame,
            frame_id=None,
            sensor_frame=None,
            sensor_geometry=None,
        ):
            assert frame_id == 23
            return FrameObservationResult(
                frame_id=23,
                events=tuple(
                    quantitative23
                ),
                changed=False,
                text=None,
            )

        observer.process_frame = tx23_process

        try:
            live.process_frame_transaction(
                observer,
                image.copy(),
                Path(
                    "/tmp/"
                    "hero_delayed_stack_23.png"
                ),
                23,
                state,
            )
        finally:
            observer.process_frame = original_process

        actions = (
            observer.hand.semantic_actions()
        )

        new_actions = actions[before:]

        assert len(new_actions) == 1
        assert new_actions[0]["seat"] == "hero"

        assert observer.hand.next_actor == "bb"

        assert (
            state.hero_completion_pending_frame
            is None
        )

        print(
            "FRAME 23 HERO ACTION "
            "CONFIRMED AND ADMITTED: PASS"
        )

        # BB objectively folds so PREFLOP is complete.
        folded = (
            observer.admit_card_disappearance(
                "bb",
                frame_id=23,
                physical_type=(
                    "OPPONENT_CARDS_DISAPPEARED"
                ),
            )
        )

        assert folded
        assert observer.hand.next_actor is None

        # ----------------------------------------------------
        # FRAME 24
        # Subsequent FLOP is now free to advance.
        # ----------------------------------------------------

        original_process = observer.process_frame

        def tx24_process(
            frame,
            frame_id=None,
            sensor_frame=None,
            sensor_geometry=None,
        ):
            assert frame_id == 24

            return FrameObservationResult(
                frame_id=24,
                events=(
                    {
                        "frame": 24,
                        "type":
                            "FLOP_BOUNDARY_PHYSICAL",
                        "board_count": 3,
                        "previous_board_count": 1,
                    },
                ),
                changed=False,
                text=None,
            )

        observer.process_frame = tx24_process

        try:
            live.process_frame_transaction(
                observer,
                image.copy(),
                Path(
                    "/tmp/"
                    "hero_delayed_stack_24.png"
                ),
                24,
                state,
            )
        finally:
            observer.process_frame = original_process

        assert (
            state.board_identity_reader.future
            is not None
        )

        board_release.set()

        completed = None

        for _ in range(100):
            completed = (
                state.board_identity_reader
                .collect_ready()
            )

            if completed is not None:
                break

            Event().wait(0.01)

        assert completed is not None

        assert (
            live.apply_async_board_identity_result(
                observer,
                completed,
            )
            is True
        )

        assert observer.hand.street == "FLOP"

        assert observer.hand.board == [
            "Jd",
            "9s",
            "Tc",
        ]

        print(
            "FRAME 24 FLOP ADVANCED: PASS"
        )

        print(
            "HERO COMPLETION DELAYED STACK "
            "TRANSITION: PASS"
        )

    finally:
        board_release.set()

        state.board_identity_reader.close()

        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.action_buttons_visible = original_buttons
        fho.hero_cards_visible = original_hero_cards
        fho.count_board_cards = original_board_count
        live.read_board_identity = original_board_reader


if __name__ == "__main__":
    main()
