"""
V0.17 acquisition-frame transition baseline contract.

Bootstrap must establish physical transition state without processing
the acquisition frame as a semantic action frame.
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
      "real_acr_hand_2826874674/frame_0009.png"
)


def main():
    image = cv2.imread(str(FRAME))
    assert image is not None, FRAME

    observer = build_observer_from_frame(
        image,
        FRAME,
        hand_id="acquisition-baseline-contract",
    )

    assert observer is not None

    expected_opponents = set(
        observer.opponent_seats
    )

    assert set(
        observer.previous_visibility
    ) == expected_opponents

    assert all(
        isinstance(value, bool)
        for value
        in observer.previous_visibility.values()
    )

    assert (
        observer.previous_hero_cards_visible
        is True
    )

    assert (
        observer.previous_action_buttons_visible
        is not None
    )

    # Acquisition baseline itself must not manufacture physical events.
    assert observer.events == []

    # Bootstrap semantic state remains only the authoritative forced
    # contributions already created by HandEngine initialization.
    actions = observer.hand.semantic_actions()

    assert [
        row["action"]
        for row in actions
    ] == [
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    ]

    print(
        "OPPONENT ACQUISITION VISIBILITY BASELINED: PASS"
    )
    print(
        "HERO ACQUISITION VISIBILITY BASELINED: PASS"
    )
    print(
        "BOOTSTRAP PHYSICAL EVENTS EMITTED: NO"
    )
    print(
        "BOOTSTRAP SEMANTIC ACTIONS ADDED: NO"
    )
    print(
        "V0.17 ACQUISITION TRANSITION BASELINE: PASS"
    )


if __name__ == "__main__":
    main()
