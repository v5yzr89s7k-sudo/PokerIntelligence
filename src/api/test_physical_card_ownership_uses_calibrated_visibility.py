from pathlib import Path
from unittest.mock import patch

import cv2

from src.api import api_event_coordinator as coordinator
from src.events.local_event_detector import ChangeSet


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260722_152155"
)


def frame(number):
    path = SESSION / f"{number:04d}_full.png"

    image = cv2.imread(str(path))

    assert image is not None, path

    if (
        image.shape[1] != 934
        or image.shape[0] != 696
    ):
        image = cv2.resize(
            image,
            (934, 696),
        )

    return image


def main():
    # Frame 0001 is decisive:
    #
    # legacy dealt_in_seats incorrectly excludes HJ/CO,
    # while the calibrated opponent-card detector sees both.
    first = frame(1)

    legacy = coordinator.dealt_in_seats(
        first,
        coordinator.GEOM,
    )

    print(
        "legacy visible =",
        legacy,
    )

    assert (
        "seat_upper_right"
        not in legacy
    )

    assert (
        "seat_mid_right"
        not in legacy
    )

    state = {
        "phase": "PREFLOP",
        "hand_token": "calibrated-ownership",
        "terminal_action_frozen": False,
        "physical_card_action_ownership": None,
    }

    emitted = []

    coordinator.process_current_frame_physical_card_ownership(
        state,
        first,
        ChangeSet(),
        street="PREFLOP",
        hero_owned=True,
    )

    ownership = (
        state.get(
            "physical_card_action_ownership"
        )
        or {}
    )

    visible = list(
        ownership.get("visible_seats")
        or []
    )

    print(
        "owned visible =",
        visible,
    )

    assert (
        "seat_upper_right"
        in visible
    ), (
        "physical-card ownership did not use "
        "calibrated HJ card-back visibility"
    )

    assert (
        "seat_mid_right"
        in visible
    ), (
        "physical-card ownership did not use "
        "calibrated CO card-back visibility"
    )

    # Frame 0040 contains the real simultaneous HJ/CO
    # visible -> absent transition.
    before = frame(39)
    after = frame(40)

    detector = coordinator.LocalEventDetector()

    detector.detect(before)
    changes = detector.detect(after)

    disappeared = list(
        changes
        .opponent_hole_cards_disappeared_seats
        or []
    )

    print(
        "disappeared =",
        disappeared,
    )

    assert (
        "seat_upper_right"
        in disappeared
    )

    assert (
        "seat_mid_right"
        in disappeared
    )

    emitted = []

    with patch.object(
        coordinator,
        "emit",
        side_effect=lambda event: emitted.append(
            event
        ),
    ):
        coordinator.process_current_frame_physical_card_ownership(
            state,
            after,
            changes,
            street="PREFLOP",
            hero_owned=True,
        )

    completions = [
        event
        for event in emitted
        if event.get("type")
        == "physical_actor_completed"
    ]

    completion_seats = [
        event.get("seat")
        for event in completions
    ]

    print(
        "completion seats =",
        completion_seats,
    )

    assert (
        "seat_upper_right"
        in completion_seats
    )

    assert (
        "seat_mid_right"
        in completion_seats
    )

    print()
    print(
        "PASS: physical-card ownership and "
        "disappearance use one calibrated "
        "opponent-card visibility definition"
    )


if __name__ == "__main__":
    main()
