"""
Regression:

Pre-acquisition stack evidence must never become acquisition quantitative
authority merely because acquisition-frame OCR is unresolved.

Forced bets can occur between those observations and Hero acquisition.
"""

from pathlib import Path

import cv2

from src.v017.run_live_observer import (
    build_observer_from_frame,
)


ROOT = Path(__file__).resolve().parents[2]

FRAME = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "controlled_hand_2826921615/"
      "frame_0012.png"
)


def main():
    image = cv2.imread(
        str(FRAME)
    )

    assert image is not None, FRAME

    participants = (
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
    )

    stale = {
        "seat_top": 44.83,
        "seat_upper_right": 57.43,
        "seat_mid_right": 135.95,
        "seat_lower_right": 59.18,
        "hero": 21.41,
        "seat_lower_left": 179.63,
        "seat_mid_left": 116.22,
        "seat_upper_left": 48.76,
    }

    observer = build_observer_from_frame(
        image,
        FRAME,
        hand_id=
            "acquisition-stale-authority-regression",
        frozen_participants=participants,
        frozen_stack_authority=stale,
    )

    assert observer is not None

    print(
        "trusted_stacks =",
        observer.trusted_stacks,
    )

    # Acquisition pixels now resolve seat_top directly.
    # The stale pre-acquisition 44.83 value must not survive.
    observed = observer.trusted_stacks.get(
        "seat_top"
    )

    assert observed is not None

    assert abs(
        float(observed) - 44.71
    ) < 0.001, observed

    assert abs(
        float(observed) - 44.83
    ) > 0.001

    assert (
        "seat_top"
        in observer.quantitative_seats
    )

    player = observer.hand.players[
        "seat_top"
    ]

    print(
        "seat_top starting_stack_bb =",
        player.starting_stack_bb,
    )

    assert (
        player.starting_stack_bb
        is not None
    )

    assert abs(
        float(player.starting_stack_bb)
        - 44.71
    ) < 0.001

    # Seats physically resolved on acquisition remain authoritative.
    assert abs(
        observer.trusted_stacks[
            "hero"
        ]
        - 21.41
    ) < 0.001

    assert abs(
        observer.trusted_stacks[
            "seat_upper_left"
        ]
        - 48.76
    ) < 0.001

    print()
    print(
        "STALE PRE-ACQUISITION AUTHORITY REJECTION: PASS"
    )


if __name__ == "__main__":
    main()
