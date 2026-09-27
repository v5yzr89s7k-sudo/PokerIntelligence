"""
Regression: authoritative dealt-in participation may seed opponent-card
presence provenance for disappearance ownership.

A frozen participant is already independently established as participating
in this hand. Acquisition-frame card visibility may false-negative.

Contract:
    dealt_in opponent + acquisition card false-negative
    + two independent absent physical frames
    -> exactly one OPPONENT_CARDS_DISAPPEARED event.

This does not grant semantic fold authority. It establishes only the
physical disappearance proposition; semantic admission remains downstream.
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
        participant_provenance_seats=[
            "utg",
            "btn",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="dealt-in-absence-provenance",
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

    obs = observer()

    seat_by_geometry = {
        id(obs.geometry["hole_cards"][seat]): seat
        for seat in obs.opponent_seats
    }

    physical = {
        "utg": True,
        "btn": False,
        "sb": True,
        "bb": True,
    }

    def fake_cards(frame, regions):
        return physical[
            seat_by_geometry[id(regions)]
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
        obs.establish_physical_transition_baseline(
            image,
            physical_geometry=obs.geometry,
            native_frame=image,
        )

        print(
            "btn_dealt_in =",
            obs.hand.players["btn"].dealt_in,
        )
        print(
            "btn_raw_presence =",
            "btn"
            in obs.opponent_card_presence_confirmed,
        )

        assert (
            obs.hand.players["btn"].dealt_in
            is True
        )

        # Acquisition detector intentionally false-negatives.
        assert (
            "btn"
            not in obs.opponent_card_presence_confirmed
        )

        first = obs.process_frame(
            image.copy(),
            frame_id=1,
            sensor_frame=image.copy(),
            sensor_geometry=obs.geometry,
        )

        assert events_for(first, "btn") == []

        second = obs.process_frame(
            image.copy(),
            frame_id=2,
            sensor_frame=image.copy(),
            sensor_geometry=obs.geometry,
        )

        disappeared = events_for(
            second,
            "btn",
        )

        print(
            "disappearance_events =",
            disappeared,
        )

        assert len(disappeared) == 1, (
            "dealt-in participant with acquisition "
            "card false-negative cannot establish "
            "persistent physical disappearance"
        )

        third = obs.process_frame(
            image.copy(),
            frame_id=3,
            sensor_frame=image.copy(),
            sensor_geometry=obs.geometry,
        )

        assert events_for(third, "btn") == []

        print(
            "V0.17 DEALT-IN ABSENCE PROVENANCE: PASS"
        )

    finally:
        fho.opponent_cards_visible = original_cards
        fho.hero_cards_visible = original_hero
        fho.count_board_cards = original_board


if __name__ == "__main__":
    main()
