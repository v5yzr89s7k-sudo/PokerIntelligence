from src.v017.chronology_completion import (
    predecessors_before_actor,
    remaining_before_street_boundary,
)


def main():
    # FLOP:
    # Hero -> BB -> BTN.
    #
    # Observing BB's later physical chip commitment proves Hero
    # completed before BB.
    pending = [
        "hero",
        "seat_lower_left",
        "seat_lower_right",
    ]

    completed = predecessors_before_actor(
        pending,
        "seat_lower_left",
    )

    assert completed == [
        "hero"
    ]

    print(
        "flop BB evidence proves completed predecessors =",
        completed,
    )

    # After flop finishes, TURN begins Hero -> BB.
    # If the RIVER board physically appears while both remain
    # pending and neither generated quantitative/fold evidence,
    # both must have completed before that street boundary.
    pending_turn = [
        "hero",
        "seat_lower_left",
    ]

    completed = (
        remaining_before_street_boundary(
            pending_turn
        )
    )

    assert completed == [
        "hero",
        "seat_lower_left",
    ]

    print(
        "river boundary proves completed turn actors =",
        completed,
    )

    # River:
    # observing BB's physical commitment again proves Hero
    # completed first.
    pending_river = [
        "hero",
        "seat_lower_left",
    ]

    completed = predecessors_before_actor(
        pending_river,
        "seat_lower_left",
    )

    assert completed == [
        "hero"
    ]

    print(
        "river BB evidence proves completed predecessors =",
        completed,
    )

    # The helper itself must never classify CHECK/FOLD/etc.
    print()
    print(
        "V0.17 CHRONOLOGY COMPLETION: PASS"
    )


if __name__ == "__main__":
    main()
