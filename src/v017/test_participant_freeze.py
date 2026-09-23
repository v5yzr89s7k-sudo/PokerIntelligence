from src.v017.participant_freeze import (
    ParticipantFreeze,
)


EIGHT = (
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
)

SEVEN = tuple(
    seat
    for seat in EIGHT
    if seat != "seat_top"
)

SIX = (
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_mid_left",
)


def main():
    freeze = ParticipantFreeze(3)

    assert freeze.observe(EIGHT) is None
    assert freeze.observe(EIGHT) is None
    assert freeze.observe(EIGHT) == EIGHT

    # Once frozen, later false negatives cannot rewrite topology.
    assert freeze.observe(SEVEN) == EIGHT
    assert freeze.participants == EIGHT

    freeze = ParticipantFreeze(3)

    false_positive = tuple(
        list(SIX)
        + ["seat_lower_left"]
    )

    assert (
        freeze.observe(
            false_positive
        )
        is None
    )

    assert freeze.observe(SIX) is None
    assert freeze.observe(SIX) is None
    assert freeze.observe(SIX) == SIX

    authority = ParticipantFreeze(3)

    authority.observe_stack_authority(
        [
            {
                "seat": "seat_top",
                "stack_bb": 44.83,
            },
            {
                "seat": "hero",
                "stack_bb": 21.54,
            },
        ],
        frame="frame_0001.png",
    )

    # Unresolved later evidence cannot erase prior authority.
    authority.observe_stack_authority(
        [
            {
                "seat": "seat_top",
                "stack_bb": None,
            },
            {
                "seat": "hero",
                "stack_bb": 21.41,
            },
        ],
        frame="frame_0011.png",
    )

    assert authority.trusted_stacks[
        "seat_top"
    ] == 44.83

    assert authority.trusted_stacks[
        "hero"
    ] == 21.41

    print(
        "PARTICIPANT FREEZE: PASS"
    )


if __name__ == "__main__":
    main()
