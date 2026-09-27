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


def observe_one_retry(freeze):
    frozen = freeze.observe(EIGHT)

    if frozen is None:
        return (
            tuple(freeze.fallback_participants),
            freeze.best_streak,
            freeze.is_frozen,
        )

    return (
        tuple(frozen),
        freeze.best_streak,
        freeze.is_frozen,
    )


def main():
    freeze = ParticipantFreeze(
        stable_required=3
    )

    first = observe_one_retry(freeze)
    second = observe_one_retry(freeze)
    third = observe_one_retry(freeze)

    print("first =", first)
    print("second =", second)
    print("third =", third)

    assert first == (
        EIGHT,
        1,
        False,
    )

    assert second == (
        EIGHT,
        2,
        False,
    )

    assert third == (
        EIGHT,
        3,
        True,
    )

    assert freeze.participants == EIGHT

    print(
        "PARTICIPANT FREEZE RETRY LIFETIME: PASS"
    )


if __name__ == "__main__":
    main()
