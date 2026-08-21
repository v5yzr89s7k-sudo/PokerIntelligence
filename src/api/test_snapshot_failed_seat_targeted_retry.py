from unittest.mock import patch

from src.api import table_snapshot_reader_core_v2 as s


def main():
    cards = [
        {
            "seat": "seat_upper_right",
            "image": None,
            "occupancy_confidence": 0.9,
        },
        {
            "seat": "seat_mid_right",
            "image": None,
            "occupancy_confidence": 0.9,
        },
    ]

    fresh_players = {
        "seat_upper_right": {
            "seat": "seat_upper_right",
            "name": "Twib101",
            "stack_text": "",
            "stack_bb": None,
            "is_hero": False,
            "is_active": True,
        },
        "seat_mid_right": {
            "seat": "seat_mid_right",
            "name": "",
            "stack_text": "",
            "stack_bb": None,
            "is_hero": False,
            "is_active": True,
        },
    }

    missing = [
        cards[1],
    ]

    calls = []

    def fake_request(cards_arg, dealer):
        calls.append(
            [card["seat"] for card in cards_arg]
        )

        assert len(cards_arg) == 1
        assert (
            cards_arg[0]["seat"]
            == "seat_mid_right"
        )

        return {
            "players": [
                {
                    "seat": "seat_mid_right",
                    "name": "Pablopg",
                    "stack_text": "",
                    "stack_bb": None,
                    "is_hero": False,
                    "is_active": True,
                }
            ],
            "api_ms": 1200.0,
            "parse_ms": 0.1,
            "image_bytes": 100,
            "confidence": 1.0,
        }

    retry_fn = getattr(
        s,
        "retry_unresolved_opponent_names",
        None,
    )

    assert retry_fn is not None, (
        "REPRODUCED: snapshot has no targeted "
        "unresolved-opponent API retry"
    )

    with patch.object(
        s,
        "_request_cards_api",
        side_effect=fake_request,
    ):
        result = retry_fn(
            fresh_players,
            missing,
            "seat_lower_right",
        )

    print("calls:", calls)
    print(
        "mid-right:",
        fresh_players["seat_mid_right"],
    )
    print("result:", result)

    assert calls == [
        ["seat_mid_right"]
    ], (
        "targeted retry must request only "
        "the unresolved physical seat"
    )

    assert (
        fresh_players[
            "seat_mid_right"
        ]["name"]
        == "Pablopg"
    )

    print(
        "PASS: unresolved opponent receives "
        "one targeted API retry"
    )


if __name__ == "__main__":
    main()
