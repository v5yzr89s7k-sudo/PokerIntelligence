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

OPPONENTS_ONLY = tuple(
    seat
    for seat in EIGHT
    if seat != "hero"
)


def hero_visible_fallback(
    observations,
):
    freeze = ParticipantFreeze(
        stable_required=3
    )

    for index, participants in enumerate(
        observations
    ):
        frozen = freeze.observe(
            participants
        )

        hero_visible = (
            index
            == len(observations) - 1
        )

        if not hero_visible:
            continue

        if frozen is None:
            frozen = (
                freeze.fallback_participants
            )

        if frozen is None:
            frozen = tuple(
                participants
            )

        fallback = set(
            frozen
        )
        fallback.add("hero")

        frozen = tuple(
            seat
            for seat in EIGHT
            if seat in fallback
        )

        return (
            tuple(frozen),
            freeze,
        )

    raise AssertionError(
        "missing Hero-visible observation"
    )


def main():
    print(
        "===== TRANSIENT FINAL FALSE NEGATIVE ====="
    )

    frozen, freeze = (
        hero_visible_fallback(
            [
                EIGHT,
                EIGHT,
                SEVEN,
            ]
        )
    )

    print("frozen =", frozen)
    print(
        "best_candidate =",
        freeze.best_candidate,
    )
    print(
        "best_streak =",
        freeze.best_streak,
    )

    assert frozen == EIGHT
    assert freeze.best_streak == 2

    print(
        "TWO-FRAME EIGHT-SEAT SUPPORT SURVIVES "
        "FINAL TRANSIENT MISS: PASS"
    )

    print()
    print(
        "===== NORMAL THREE-FRAME EIGHT ====="
    )

    frozen, freeze = (
        hero_visible_fallback(
            [
                EIGHT,
                EIGHT,
                EIGHT,
            ]
        )
    )

    assert frozen == EIGHT
    assert freeze.is_frozen

    print(
        "STABLE EIGHT-HANDED FREEZE: PASS"
    )

    print()
    print(
        "===== LEGITIMATE THREE-FRAME SEVEN ====="
    )

    frozen, freeze = (
        hero_visible_fallback(
            [
                SEVEN,
                SEVEN,
                SEVEN,
            ]
        )
    )

    assert frozen == SEVEN
    assert freeze.is_frozen

    print(
        "STABLE SEVEN-HANDED TABLE PRESERVED: PASS"
    )

    print()
    print(
        "===== ONE OBSERVATION ONLY ====="
    )

    frozen, freeze = (
        hero_visible_fallback(
            [
                SEVEN,
            ]
        )
    )

    assert frozen == SEVEN
    assert freeze.best_streak == 1

    print(
        "INITIAL ATTACH FALLBACK PRESERVED: PASS"
    )

    print()
    print(
        "===== HERO OCCUPANCY FALSE NEGATIVE ====="
    )

    frozen, freeze = (
        hero_visible_fallback(
            [
                OPPONENTS_ONLY,
            ]
        )
    )

    print(
        "observed =",
        OPPONENTS_ONLY,
    )
    print(
        "frozen =",
        frozen,
    )
    print(
        "best_streak =",
        freeze.best_streak,
    )

    assert "hero" not in OPPONENTS_ONLY
    assert frozen == EIGHT
    assert freeze.best_streak == 1
    assert not freeze.is_frozen

    print(
        "HERO-VISIBLE FALLBACK MERGES "
        "TRANSIENT HERO OCCUPANCY MISS: PASS"
    )

    print()
    print(
        "V0.17 HERO-VISIBLE TOPOLOGY FALLBACK: PASS"
    )


if __name__ == "__main__":
    main()
