def dealer_confirmed(observations, required=2):
    if len(observations) < required:
        return None

    tail = observations[-required:]

    seats = [
        row["dealer_button_seat"]
        for row in tail
        if row.get("found")
    ]

    if len(seats) != required:
        return None

    if len(set(seats)) != 1:
        return None

    return seats[0]


def main():
    # Physical recording reproduced transient false Hero ownership.
    observations = [
        {"found": True, "dealer_button_seat": "seat_lower_left"},
        {"found": True, "dealer_button_seat": "hero"},
    ]

    assert dealer_confirmed(observations) is None

    observations.append(
        {"found": True, "dealer_button_seat": "seat_lower_left"}
    )

    assert dealer_confirmed(observations) is None

    observations.append(
        {"found": True, "dealer_button_seat": "seat_lower_left"}
    )

    assert (
        dealer_confirmed(observations)
        == "seat_lower_left"
    )

    print("DEALER TEMPORAL CONFIRMATION CONTRACT: PASS")


if __name__ == "__main__":
    main()
