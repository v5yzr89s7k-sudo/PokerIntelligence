"""
Regression for the Oct-8 Jd6s live-hand deadlock.

A physical FLOP may become visible before the final preflop actor's
stack text has reached its stable post-action value.

The later quantitative observation may close PREFLOP only when:
  - the FLOP boundary is still retained;
  - semantic state is still PREFLOP;
  - the seat is still the authoritative next_actor;
  - the quantitative transition is otherwise legal.

This must not authorize arbitrary post-boundary evidence to rewrite
the predecessor street.
"""

import numpy as np

import src.v017.frame_hand_observer as fho
from src.v017.frame_hand_observer import FrameHandObserver


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


PLAYERS = [
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 45.4,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 41.85,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "BB",
        "name": "Hero",
        "stack_bb": 41.65,
        "dealt_in": True,
        "is_hero": True,
    },
]


def quantitative(frame, seat, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "resolved": True,
        "resolved_value": value,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["btn", "sb", "hero"],
        small_blind_seat="sb",
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
            "btn": 45.4,
            "sb": 41.85,
            "hero": 41.65,
        },
        opponent_seats=["btn", "sb"],
        quantitative_seats=["btn", "sb", "hero"],
        hero_seat="hero",
        hand_id="oct8-jd6s-late-visible-completion",
    )

    # Reproduce the known semantic frontier immediately before the
    # deadlock: BTN has committed 2 BB, SB 0.5 BB, Hero remains the
    # final unresolved actor.
    observer.hand.observe_stack_commitment(
        "btn",
        2.0,
    )

    # SB folds; Hero is now the authoritative unresolved actor.
    observer.hand.observe_fold("sb")

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "hero"

    # Drive the real physical observer through the Oct-8 ordering:
    #
    # frame 3: board still 0, no stack motion
    # frame 4: FLOP appears AND Hero stack region physically moves,
    #          but OCR still exposes the old 41.65 baseline.
    current = {"frame": 3}

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
            current["frame"] == 4
            and seat == "hero"
        )

    def fake_resolve(reading, prior):
        return Resolution(41.65)

    def fake_board(frame, geometry):
        return (
            3
            if current["frame"] == 4
            else 0
        )

    def fake_hero(frame, geometry):
        return True

    def fake_reader(crop):
        return {
            "stack_bb": 41.65,
            "confidence": 0.80,
            "votes": 1,
            "candidates": [41.65],
        }

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
        baseline = observer.process_frame(
            image.copy(),
            frame_id=3,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

        assert not [
            event
            for event in baseline.events
            if event.get("type", "").endswith(
                "_BOUNDARY_PHYSICAL"
            )
        ]

        current["frame"] = 4

        physical = observer.process_frame(
            image.copy(),
            frame_id=4,
            sensor_frame=image.copy(),
            sensor_geometry=observer.geometry,
        )

    finally:
        fho.measure_stack_motion = original_motion
        fho.resolve_fast_stack = original_resolve
        fho.count_board_cards = original_board
        fho.hero_cards_visible = original_hero

    boundaries = [
        event
        for event in physical.events
        if event.get("type")
        == "FLOP_BOUNDARY_PHYSICAL"
    ]

    assert len(boundaries) == 1
    boundary = boundaries[0]

    provenance = (
        observer.pre_boundary_stack_motion.get(
            "hero"
        )
    )

    print("physical_boundary =", boundary)
    print("automatic_provenance =", provenance)

    assert provenance is not None
    assert provenance["frame"] == 4
    assert provenance["boundary_frame"] == 4
    assert provenance["street"] == "PREFLOP"
    assert (
        provenance["boundary_type"]
        == "FLOP_BOUNDARY_PHYSICAL"
    )

    # process_frame is perception-only. Admit the physical boundary
    # through the normal semantic boundary owner.
    result = observer.admit_street_boundary(
        boundary,
        action_order=["hero", "btn"],
        board=["2s", "4s", "8c"],
        complete_pending=False,
    )

    assert result == ()
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "hero"
    assert observer.pending_street_boundaries

    # ACR animation exposes Hero's final preflop stack only after the
    # physical flop is already visible. This is the observed Oct-8
    # 41.65 -> 40.65 transition.
    admitted = observer.admit_quantitative_observation(
        quantitative(
            9,
            "hero",
            40.65,
        )
    )

    print("admitted =", admitted)
    print("street =", observer.hand.street)
    print("next_actor =", observer.hand.next_actor)

    assert admitted, (
        "RED: current actor's late-visible physical completion "
        "was rejected solely because FLOP was already visible"
    )

    # Admission closes the predecessor betting round and the
    # retained physical FLOP is reconciled immediately. next_actor
    # therefore already belongs to FLOP; it must not be expected None.
    assert observer.hand.street == "FLOP"
    assert observer.pending_street_boundaries == []

    actions = observer.hand.semantic_actions()

    print("semantic_actions =", actions)

    hero_preflop_calls = [
        row
        for row in actions
        if (
            row.get("seat") == "hero"
            and row.get("street") == "PREFLOP"
            and row.get("action") == "CALL"
        )
    ]

    print(
        "hero_preflop_calls =",
        hero_preflop_calls,
    )

    assert len(hero_preflop_calls) == 1
    assert (
        hero_preflop_calls[0]["amount_bb"]
        == 1.0
    )

    print(
        "LATE-VISIBLE CURRENT-ACTOR BOUNDARY COMPLETION: PASS"
    )


if __name__ == "__main__":
    main()
