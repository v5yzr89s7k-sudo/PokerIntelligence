SEAT_ORDER = [
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
]

POSITIONS_BY_COUNT = {
    2: ["SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "UTG"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO"],
}

def occupied_seats(players):
    seen = set()
    seats = []
    for p in players or []:
        seat = p.get("seat")
        if seat in SEAT_ORDER and seat not in seen:
            seen.add(seat)
            seats.append(seat)
    return [s for s in SEAT_ORDER if s in seen]

def assign_positions(players, dealer_button_seat):
    seats = occupied_seats(players)
    n = len(seats)

    if (
        dealer_button_seat not in SEAT_ORDER
        or n not in POSITIONS_BY_COUNT
    ):
        return {
            seat: "unknown"
            for seat in seats
        }

    if dealer_button_seat in seats:
        # Normal live-button case: the button belongs to an occupied seat.
        btn_idx = seats.index(dealer_button_seat)
        ordered = (
            seats[btn_idx:]
            + seats[:btn_idx]
        )
        labels = POSITIONS_BY_COUNT[n]

        return {
            seat: labels[index]
            for index, seat in enumerate(ordered)
        }

    # Dead-button case: the physical dealer-button position is empty.
    #
    # Walk clockwise from the empty button through the full physical seat
    # ring, retain only occupied seats, and use the next larger table's
    # labels with BTN removed. Example with seven occupied seats:
    #
    #   empty BTN, SB, BB, UTG, UTG+1, LJ, HJ, CO
    #
    expanded_count = n + 1

    if expanded_count not in POSITIONS_BY_COUNT:
        return {
            seat: "unknown"
            for seat in seats
        }

    dealer_index = SEAT_ORDER.index(
        dealer_button_seat
    )

    physical_after_button = (
        SEAT_ORDER[dealer_index + 1:]
        + SEAT_ORDER[:dealer_index]
    )

    ordered = [
        seat
        for seat in physical_after_button
        if seat in seats
    ]

    labels = POSITIONS_BY_COUNT[
        expanded_count
    ][1:]

    if len(ordered) != len(labels):
        return {
            seat: "unknown"
            for seat in seats
        }

    return {
        seat: labels[index]
        for index, seat in enumerate(ordered)
    }



def _ordered_occupied_seats(seats):
    """
    Normalize an iterable of seat labels into canonical clockwise order.
    """
    seen = {
        seat
        for seat in (seats or [])
        if seat in SEAT_ORDER
    }
    return [
        seat
        for seat in SEAT_ORDER
        if seat in seen
    ]


def next_occupied_seat(seats, seat):
    """
    Return the next occupied seat clockwise from `seat`.
    """
    ordered = _ordered_occupied_seats(seats)

    if seat not in ordered or len(ordered) < 2:
        return None

    index = ordered.index(seat)
    return ordered[(index + 1) % len(ordered)]


def previous_occupied_seat(seats, seat):
    """
    Return the previous occupied seat counterclockwise from `seat`.
    """
    ordered = _ordered_occupied_seats(seats)

    if seat not in ordered or len(ordered) < 2:
        return None

    index = ordered.index(seat)
    return ordered[(index - 1) % len(ordered)]


def assign_positions_from_blinds(
    occupied,
    small_blind_seat,
    big_blind_seat,
):
    """
    Infer dealer/button and all table positions from locally detected blinds.

    Returns:
        {
            "valid": bool,
            "reason": str,
            "dealer_button_seat": str,
            "positions": dict,
            "hero_position": str,
            "occupied_seats": list,
            "small_blind_seat": str,
            "big_blind_seat": str,
        }

    For 3+ players:
        BTN is the occupied seat immediately before SB.

    Heads-up:
        BTN and SB are the same seat.
    """
    seats = _ordered_occupied_seats(occupied)
    count = len(seats)

    result = {
        "valid": False,
        "reason": "",
        "dealer_button_seat": "",
        "positions": {},
        "hero_position": "unknown",
        "occupied_seats": seats,
        "small_blind_seat": small_blind_seat or "",
        "big_blind_seat": big_blind_seat or "",
    }

    if count not in POSITIONS_BY_COUNT:
        result["reason"] = (
            f"unsupported occupied-seat count: {count}"
        )
        return result

    if small_blind_seat not in seats:
        result["reason"] = "small blind is not an occupied seat"
        return result

    if big_blind_seat not in seats:
        result["reason"] = "big blind is not an occupied seat"
        return result

    expected_big_blind = next_occupied_seat(
        seats,
        small_blind_seat,
    )

    if expected_big_blind != big_blind_seat:
        result["reason"] = (
            "small blind and big blind are not consecutive "
            "occupied seats"
        )
        return result

    if count == 2:
        dealer_button_seat = small_blind_seat
    else:
        dealer_button_seat = previous_occupied_seat(
            seats,
            small_blind_seat,
        )

    players = [
        {"seat": seat}
        for seat in seats
    ]

    positions = assign_positions(
        players,
        dealer_button_seat,
    )

    if (
        positions.get(small_blind_seat) != "SB"
        or positions.get(big_blind_seat) != "BB"
    ):
        result["reason"] = (
            "derived position map does not agree with "
            "observed blind seats"
        )
        return result

    result.update({
        "valid": True,
        "reason": "positions derived from local blind observations",
        "dealer_button_seat": dealer_button_seat,
        "positions": positions,
        "hero_position": positions.get(
            "hero",
            "unknown",
        ),
    })

    return result
