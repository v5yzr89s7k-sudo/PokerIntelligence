from itertools import combinations

from src.api.position_engine import (
    SEAT_ORDER,
    POSITIONS_BY_COUNT,
    assign_positions,
)


def players_for(seats):
    return [
        {
            "seat": seat,
            "name": f"player_{seat}",
            "stack_bb": 100.0,
            "is_active": True,
            "is_hero": seat == "hero",
        }
        for seat in seats
    ]


def expected_positions(seats, dealer):
    """
    Independent poker reference:

    Start with BTN at the occupied dealer seat.
    Walk clockwise through OCCUPIED seats only.

    Empty physical chairs do NOT retain poker positions.
    Positions compress according to player count.
    """
    occupied = [
        seat
        for seat in SEAT_ORDER
        if seat in set(seats)
    ]

    if dealer not in occupied:
        raise AssertionError(
            f"test requires occupied dealer: {dealer}"
        )

    dealer_index = occupied.index(dealer)

    ordered = (
        occupied[dealer_index:]
        + occupied[:dealer_index]
    )

    labels = POSITIONS_BY_COUNT[len(occupied)]

    return {
        seat: labels[index]
        for index, seat in enumerate(ordered)
    }


def check_case(seats, dealer):
    players = players_for(seats)

    expected = expected_positions(
        seats,
        dealer,
    )

    normal = assign_positions(
        players,
        dealer,
    )

    preserved = assign_positions(
        players,
        dealer,
        preserve_physical_slots=True,
    )

    if normal != expected:
        print()
        print("NORMAL ASSIGNMENT FAILURE")
        print("players :", len(seats))
        print("dealer  :", dealer)
        print("seats   :", seats)
        print("expected:", expected)
        print("actual  :", normal)
        raise AssertionError(
            "normal position assignment is poker-incorrect"
        )

    return preserved != expected


def test_all_table_sizes():
    total = 0
    preserve_failures = {
        8: 0,
        7: 0,
        6: 0,
    }

    examples = {}

    for player_count in (8, 7, 6):

        for occupied_tuple in combinations(
            SEAT_ORDER,
            player_count,
        ):
            occupied = list(occupied_tuple)

            for dealer in occupied:
                total += 1

                preserve_wrong = check_case(
                    occupied,
                    dealer,
                )

                if preserve_wrong:
                    preserve_failures[player_count] += 1

                    examples.setdefault(
                        player_count,
                        {
                            "seats": occupied,
                            "dealer": dealer,
                            "correct": expected_positions(
                                occupied,
                                dealer,
                            ),
                            "preserved": assign_positions(
                                players_for(occupied),
                                dealer,
                                preserve_physical_slots=True,
                            ),
                        },
                    )

    print()
    print("=" * 72)
    print("VARIABLE TABLE-SIZE POSITION TEST")
    print("=" * 72)
    print(f"cases checked: {total}")
    print()

    for player_count in (8, 7, 6):
        print(
            f"{player_count}-handed "
            f"preserve_physical_slots disagreements: "
            f"{preserve_failures[player_count]}"
        )

        example = examples.get(player_count)

        if example:
            print("  example seats     :", example["seats"])
            print("  dealer            :", example["dealer"])
            print("  correct compressed:", example["correct"])
            print("  physical preserved:", example["preserved"])

        print()

    assert preserve_failures[8] == 0, (
        "8-handed physical and compressed mappings "
        "should be identical"
    )

    assert preserve_failures[7] > 0, (
        "expected physical-slot preservation to disagree "
        "with real seven-handed poker positions"
    )

    assert preserve_failures[6] > 0, (
        "expected physical-slot preservation to disagree "
        "with real six-handed poker positions"
    )

    print(
        "PASS: normal position assignment compresses correctly "
        "for every tested 8/7/6-handed occupied-seat topology."
    )

    print(
        "CONFIRMED: preserve_physical_slots is incompatible "
        "with variable-handed poker position assignment."
    )


if __name__ == "__main__":
    test_all_table_sizes()
