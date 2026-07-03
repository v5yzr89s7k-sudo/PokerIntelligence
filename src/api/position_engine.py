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

    if dealer_button_seat not in seats or n not in POSITIONS_BY_COUNT:
        return {s: "unknown" for s in seats}

    btn_idx = seats.index(dealer_button_seat)
    ordered = seats[btn_idx:] + seats[:btn_idx]
    labels = POSITIONS_BY_COUNT[n]

    return {seat: labels[i] for i, seat in enumerate(ordered)}
