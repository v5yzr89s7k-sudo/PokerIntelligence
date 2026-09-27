"""
Opponent card disappearance requires positive presence provenance.

Safe physical proposition:

    cards were independently observed PRESENT in this hand
    then later independently observed ABSENT

Unsafe proposition:

    cards were absent at acquisition
    and remained absent

Persistent absence without prior positive presence must never create
OPPONENT_CARDS_DISAPPEARED ownership.
"""

import numpy as np

import src.v017.frame_hand_observer as fho

from src.v017.frame_hand_observer import FrameHandObserver


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
        "position": "CO",
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
        "stack_bb": 30.0,
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


def make_observer():
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
            "sb": 30.0,
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
        hand_id="card-presence-provenance",
    )


def disappeared(result, seat):
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

    geometry_to_seat = {}

    def fake_cards(frame, regions):
        return physical[
            geometry_to_seat[id(regions)]
        ]

    def fake_hero(frame, geometry):
        return True

    def fake_board(frame, geometry):
        return 0

    fho.opponent_cards_visible = fake_cards
    fho.hero_cards_visible = fake_hero
    fho.count_board_cards = fake_board

    image = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    try:
        # ====================================================
        # CASE 1
        #
        # BTN is already absent at acquisition and remains
        # absent. This MUST NOT become disappearance evidence.
        # ====================================================

        obs = make_observer()

        for seat in obs.opponent_seats:
            geometry_to_seat[
                id(obs.geometry["hole_cards"][seat])
            ] = seat

        obs.establish_physical_transition_baseline(
            image,
            physical_geometry=obs.geometry,
            native_frame=image,
        )

        for frame_id in (1, 2, 3, 4):
            result = obs.process_frame(
                image.copy(),
                frame_id=frame_id,
                sensor_frame=image.copy(),
                sensor_geometry=obs.geometry,
            )

            assert disappeared(
                result,
                "btn",
            ) == [], (
                "RED: persistent absence without prior "
                "positive card presence created fold evidence"
            )

        assert (
            "btn"
            not in obs.opponent_card_absence_confirmed
        ), (
            "RED: absent-at-acquisition seat became confirmed "
            "disappearance without prior positive presence"
        )

        print(
            "ABSENT WITHOUT PRIOR PRESENCE "
            "HAS NO FOLD AUTHORITY: PASS"
        )

        # ====================================================
        # CASE 2
        #
        # Independent positive presence first, then two absent
        # observations. This MUST produce exactly one event.
        # ====================================================

        obs2 = make_observer()

        geometry_to_seat.clear()

        for seat in obs2.opponent_seats:
            geometry_to_seat[
                id(obs2.geometry["hole_cards"][seat])
            ] = seat

        physical["btn"] = True

        obs2.establish_physical_transition_baseline(
            image,
            physical_geometry=obs2.geometry,
            native_frame=image,
        )

        # One normal visible frame establishes independent
        # positive presence provenance.
        result1 = obs2.process_frame(
            image.copy(),
            frame_id=1,
            sensor_frame=image.copy(),
            sensor_geometry=obs2.geometry,
        )

        assert disappeared(
            result1,
            "btn",
        ) == []

        physical["btn"] = False

        result2 = obs2.process_frame(
            image.copy(),
            frame_id=2,
            sensor_frame=image.copy(),
            sensor_geometry=obs2.geometry,
        )

        assert disappeared(
            result2,
            "btn",
        ) == []

        result3 = obs2.process_frame(
            image.copy(),
            frame_id=3,
            sensor_frame=image.copy(),
            sensor_geometry=obs2.geometry,
        )

        assert len(
            disappeared(
                result3,
                "btn",
            )
        ) == 1, (
            "RED: proven-visible opponent did not emit "
            "disappearance after independent absence confirmation"
        )

        result4 = obs2.process_frame(
            image.copy(),
            frame_id=4,
            sensor_frame=image.copy(),
            sensor_geometry=obs2.geometry,
        )

        assert disappeared(
            result4,
            "btn",
        ) == []

        print(
            "PROVEN PRESENCE -> CONFIRMED ABSENCE: PASS"
        )

        print(
            "OPPONENT CARD PRESENCE PROVENANCE: PASS"
        )

    finally:
        fho.opponent_cards_visible = original_cards
        fho.hero_cards_visible = original_hero
        fho.count_board_cards = original_board


if __name__ == "__main__":
    main()
