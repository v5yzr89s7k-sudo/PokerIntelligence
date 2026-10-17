"""
Live regression contract from 2026-10-15.

A retained Hero disappearance must lose fold authority when later
positive Hero-active physical evidence proves Hero remains in hand.
Opponent disappearance evidence must remain untouched.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


def main():
    observer = object.__new__(
        FrameHandObserver
    )

    observer.hero_seat = "hero"

    observer.pending_card_disappearances = [
        {
            "seat": "hero",
            "frame_id": 465,
            "physical_type":
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
        },
        {
            "seat": "villain",
            "frame_id": 466,
            "physical_type":
                "OPPONENT_CARDS_DISAPPEARED",
        },
    ]

    invalidated = (
        observer
        .invalidate_retained_hero_disappearance(
            frame_id=468,
            reason="action_buttons_visible",
        )
    )

    assert len(invalidated) == 1
    assert invalidated[0]["seat"] == "hero"
    assert invalidated[0]["frame_id"] == 465

    assert observer.pending_card_disappearances == [
        {
            "seat": "villain",
            "frame_id": 466,
            "physical_type":
                "OPPONENT_CARDS_DISAPPEARED",
        },
    ]

    # A same-frame/future disappearance must not be retired by an
    # earlier positive-active observation.
    observer.pending_card_disappearances.append(
        {
            "seat": "hero",
            "frame_id": 470,
            "physical_type":
                "HERO_CARDS_DISAPPEARED_PHYSICAL",
        }
    )

    again = (
        observer
        .invalidate_retained_hero_disappearance(
            frame_id=468,
            reason="action_buttons_visible",
        )
    )

    assert again == ()

    assert any(
        row["seat"] == "hero"
        and row["frame_id"] == 470
        for row
        in observer.pending_card_disappearances
    )

    print(
        "HERO REAPPEARANCE INVALIDATES "
        "RETAINED FOLD: PASS"
    )
    print(
        "OPPONENT RETAINED DISAPPEARANCE "
        "PRESERVED: PASS"
    )
    print(
        "FUTURE HERO DISAPPEARANCE "
        "PRESERVED: PASS"
    )


if __name__ == "__main__":
    main()
