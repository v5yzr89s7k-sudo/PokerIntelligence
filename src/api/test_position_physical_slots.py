from src.api.position_engine import assign_positions


def main():
    # Replay 0001:
    # physical seat_upper_right is the empty LJ chair.
    players = [
        {"seat": "seat_top"},
        {"seat": "seat_mid_right"},
        {"seat": "seat_lower_right"},
        {"seat": "hero"},
        {"seat": "seat_lower_left"},
        {"seat": "seat_mid_left"},
        {"seat": "seat_upper_left"},
    ]

    positions = assign_positions(
        players,
        "hero",
        preserve_physical_slots=True,
    )

    expected = {
        "hero": "BTN",
        "seat_lower_left": "SB",
        "seat_mid_left": "BB",
        "seat_upper_left": "UTG",
        "seat_top": "UTG+1",
        "seat_mid_right": "HJ",
        "seat_lower_right": "CO",
    }

    assert positions == expected, (
        positions,
        expected,
    )

    # Compatibility: default behavior remains count-based.
    compressed = assign_positions(
        players,
        "hero",
    )

    assert compressed["hero"] == "BTN"
    assert compressed["seat_top"] == "LJ"

    print(
        "PASS physical position slots: "
        "empty LJ preserved without changing default semantics"
    )


if __name__ == "__main__":
    main()
