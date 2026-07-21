from src.api.snapshot_identity_guard import (
    validate_unique_player_identities,
)


def test_unique_players_pass():
    players = [
        {"seat": "seat_top", "name": "Alice"},
        {"seat": "seat_upper_right", "name": "Bob"},
        {"seat": "hero", "name": "Hero"},
    ]

    assert validate_unique_player_identities(players) is True


def test_empty_names_are_ignored():
    players = [
        {"seat": "seat_top", "name": ""},
        {"seat": "seat_upper_right", "name": ""},
    ]

    assert validate_unique_player_identities(players) is True


def test_duplicate_name_across_seats_fails():
    players = [
        {"seat": "seat_top", "name": "Alice"},
        {"seat": "seat_mid_right", "name": "Alice"},
    ]

    try:
        validate_unique_player_identities(players)
    except RuntimeError as exc:
        message = str(exc)

        assert "Alice" in message
        assert "seat_top" in message
        assert "seat_mid_right" in message
    else:
        raise AssertionError(
            "duplicate player identity was not rejected"
        )


def main():
    test_unique_players_pass()
    test_empty_names_are_ignored()
    test_duplicate_name_across_seats_fails()

    print("snapshot identity guard regression passed")


if __name__ == "__main__":
    main()
