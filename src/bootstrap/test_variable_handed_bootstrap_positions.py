from src.api.position_engine import assign_positions


def main():
    # Seven-handed topology with one physical slot absent.
    #
    # Poker positions must compress around the occupied/dealt seats.
    seats = [
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
    ]

    players = [
        {"seat": seat}
        for seat in seats
    ]

    dealer = "seat_top"

    positions = assign_positions(
        players,
        dealer,
        preserve_physical_slots=False,
    )

    assert positions == {
        "seat_top": "BTN",
        "seat_upper_right": "SB",
        "seat_mid_right": "BB",
        "seat_lower_right": "UTG",
        "hero": "LJ",
        "seat_lower_left": "HJ",
        "seat_mid_left": "CO",
    }

    assert len(set(positions.values())) == 7
    assert "UTG+1" not in positions.values()

    print(
        "PASS variable-handed bootstrap positions: "
        "missing physical seats compress poker positions "
        "instead of shifting the table"
    )


if __name__ == "__main__":
    main()
