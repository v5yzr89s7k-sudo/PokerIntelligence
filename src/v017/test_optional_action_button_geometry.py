import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 10.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 10.0,
    },
]


def main():
    geometry = {
        "board_regions": {},
        "hole_cards": {},
        "stack_regions": {},
    }

    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry=geometry,
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="optional-buttons-contract",
    )

    frame = np.zeros(
        (696, 934, 3),
        dtype=np.uint8,
    )

    # Isolate the optional action-button geometry contract.
    # No action_buttons key is intentionally present.
    result = observer.process_frame(
        frame,
        frame_id=1,
        sensor_frame=frame,
        sensor_geometry=geometry,
    )

    assert result is not None

    assert (
        observer.previous_action_buttons_visible
        is False
    )

    print(
        "button state =",
        observer.previous_action_buttons_visible,
    )

    print(
        "V0.17 OPTIONAL ACTION-BUTTON GEOMETRY: PASS"
    )


if __name__ == "__main__":
    main()
