from pathlib import Path


def main():
    source = Path(
        "src/api/api_event_coordinator.py"
    ).read_text()

    assert '''authoritative_starting_roster = list(
            starting_roster_seats
            or frozen_participants
        )''' in source

    assert '''"dealt_in_seats": authoritative_starting_roster''' in source

    assert '''"card_back_dealt_in_seats": frozen_participants''' in source

    print(
        "PASS table-context starting-roster contract: "
        "hand-start occupancy owns canonical player count; "
        "card-back evidence remains separately preserved"
    )


if __name__ == "__main__":
    main()
