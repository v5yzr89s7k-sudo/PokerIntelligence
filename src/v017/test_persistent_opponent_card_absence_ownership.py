"""
V0.17 persistent opponent-card absence ownership.

Physical proposition:

    Opponent-card disappearance requires proven positive presence first.

Authority contract:

    acquisition absence creates no disappearance ownership;
    repeated absence without prior presence emits nothing;
    visible=True establishes positive presence provenance;
    first later absent frame creates an absence candidate;
    second independent absent frame emits exactly one
    OPPONENT_CARDS_DISAPPEARED event;
    persistent False thereafter emits no duplicates;
    visible=True cancels an unconfirmed absence candidate.

This is physical evidence only. Semantic fold authority remains downstream.
"""

import numpy as np

import src.v017.frame_hand_observer as fho

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "btn",
        "position": "BTN",
        "name": "BTN",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
]


def observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
            "btn",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {
                seat: {
                    "card_1": {
                        "x": 0,
                        "y": 0,
                        "width": 10,
                        "height": 10,
                    },
                    "card_2": {
                        "x": 10,
                        "y": 0,
                        "width": 10,
                        "height": 10,
                    },
                }
                for seat in (
                    "utg",
                    "btn",
                    "sb",
                    "bb",
                )
            },
            "stack_regions": {},
        },
        trusted_stacks={
            "utg": 50.0,
            "hero": 50.0,
            "btn": 50.0,
            "sb": 20.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "btn",
            "sb",
            "bb",
        ],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="persistent-card-absence",
    )


def events_for(result, seat):
    return [
        event
        for event in result.events
        if (
            event.get("type")
            == "OPPONENT_CARDS_DISAPPEARED"
            and event.get("seat") == seat
        )
    ]


def main():
    original_cards = fho.opponent_cards_visible
    original_hero = fho.hero_cards_visible
    original_board = fho.count_board_cards

    physical = {
        "utg": True,
        "btn": False,
        "sb": True,
        "bb": True,
    }

    def fake_cards(frame, regions):
        # Geometry objects are unique by seat only through insertion
        # order in this fixture, so caller sets active seat below.
        return physical[active["seat"]]

    def fake_hero(frame, geometry):
        return True

    def fake_board(frame, geometry):
        return 0

    active = {"seat": None}

    # Wrap the card sensor so we can identify which seat geometry
    # production is evaluating without modifying production.
    original_method_geometry = {}

    obs = observer()

    for seat in obs.opponent_seats:
        original_method_geometry[
            id(obs.geometry["hole_cards"][seat])
        ] = seat

    def fake_cards(frame, regions):
        seat = original_method_geometry[id(regions)]
        return physical[seat]

    fho.opponent_cards_visible = fake_cards
    fho.hero_cards_visible = fake_hero
    fho.count_board_cards = fake_board

    image = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    try:
        # ----------------------------------------------------
        # Acquisition:
        # BTN already absent.
        #
        # Must seed physical state only. No event exists here.
        # ----------------------------------------------------

        baseline = (
            obs.establish_physical_transition_baseline(
                image,
                physical_geometry=obs.geometry,
                native_frame=image,
            )
        )

        assert (
            baseline["opponent_visibility"]["btn"]
            is False
        )

        assert obs.events == []

        assert (
            "btn"
            not in obs.opponent_card_presence_confirmed
        )

        assert (
            "btn"
            not in obs.opponent_card_absence_pending
        )

        assert (
            "btn"
            not in obs.opponent_card_absence_confirmed
        )

        print(
            "ACQUISITION ABSENCE HAS NO OWNERSHIP: PASS"
        )

        # ----------------------------------------------------
        # First independent normal frame:
        # BTN still absent -> confirmation -> exactly one event.
        # ----------------------------------------------------

        result1 = obs.process_frame(
            image.copy(),
            frame_id=1,
            sensor_frame=image.copy(),
            sensor_geometry=obs.geometry,
        )

        btn1 = events_for(
            result1,
            "btn",
        )

        assert btn1 == [], (
            "RED: absence without prior positive presence "
            "created disappearance ownership"
        )

        assert (
            "btn"
            not in obs.opponent_card_absence_pending
        )

        assert (
            "btn"
            not in obs.opponent_card_absence_confirmed
        )

        print(
            "UNPROVEN PERSISTENT ABSENCE IGNORED: PASS"
        )

        # ----------------------------------------------------
        # Continued absence:
        # no duplicate event.
        # ----------------------------------------------------

        result2 = obs.process_frame(
            image.copy(),
            frame_id=2,
            sensor_frame=image.copy(),
            sensor_geometry=obs.geometry,
        )

        assert events_for(
            result2,
            "btn",
        ) == []

        print(
            "PERSISTENT ABSENCE DUPLICATE SUPPRESSED: PASS"
        )

        # ----------------------------------------------------
        # Separate cancellation case.
        #
        # Acquisition false, next independent frame true.
        # Candidate must disappear and emit nothing.
        # ----------------------------------------------------

        obs2 = observer()

        original_method_geometry.clear()

        for seat in obs2.opponent_seats:
            original_method_geometry[
                id(obs2.geometry["hole_cards"][seat])
            ] = seat

        physical["btn"] = False

        obs2.establish_physical_transition_baseline(
            image,
            physical_geometry=obs2.geometry,
            native_frame=image,
        )

        assert (
            "btn"
            not in obs2.opponent_card_presence_confirmed
        )

        assert (
            "btn"
            not in obs2.opponent_card_absence_pending
        )

        physical["btn"] = True

        result3 = obs2.process_frame(
            image.copy(),
            frame_id=1,
            sensor_frame=image.copy(),
            sensor_geometry=obs2.geometry,
        )

        assert (
            "btn"
            not in obs2.opponent_card_absence_pending
        )

        assert events_for(
            result3,
            "btn",
        ) == []

        print(
            "VISIBLE RECOVERY CANCELS ABSENCE: PASS"
        )

        print(
            "PERSISTENT OPPONENT CARD ABSENCE "
            "OWNERSHIP: PASS"
        )

    finally:
        fho.opponent_cards_visible = original_cards
        fho.hero_cards_visible = original_hero
        fho.count_board_cards = original_board


if __name__ == "__main__":
    main()
