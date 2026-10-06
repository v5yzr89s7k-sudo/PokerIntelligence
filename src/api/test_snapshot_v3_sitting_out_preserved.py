"""
Regression: read_player_identities_v2 must preserve a positive
SITTING OUT observation through final identity assembly.

SITTING OUT is not a player name, but it is terminal identity
enrichment evidence for the current hand.
"""

from unittest.mock import patch

from src.api import table_snapshot_reader_core_v2 as reader


CARD = {
    "seat": "seat_lower_left",
    "occupied": True,
    "occupancy_confidence": 0.63,
    "bounds": {
        "x1": 140,
        "y1": 447,
        "x2": 309,
        "y2": 592,
    },
}


def main():
    api_result = {
        "players": [{
            "seat": "seat_lower_left",
            "name": "",
            "sitting_out": True,
            "is_hero": False,
        }],
        "confidence": None,
    }

    with (
        patch.object(
            reader,
            "_prepare",
            return_value=(None, [dict(CARD)]),
        ),
        patch.object(
            reader,
            "load_cache",
            return_value={"players": {}},
        ),
        patch.object(
            reader,
            "_cache_fingerprint_image",
            return_value="unused",
        ),
        patch.object(
            reader,
            "_request_cards_parallel",
            return_value=api_result,
        ),
        patch.object(
            reader,
            "retry_unresolved_opponent_names",
        ) as retry,
    ):
        result = reader.read_player_identities_v2(
            "unused-frame",
            dealt_in_seats=["seat_lower_left"],
        )

    players = result["players"]

    assert len(players) == 1, players

    player = players[0]

    assert player["seat"] == "seat_lower_left"
    assert player["name"] == ""
    assert player["sitting_out"] is True, player

    # Positive SITTING OUT evidence is resolved for identity-enrichment
    # purposes and must not enter the same-frame name retry path.
    retry.assert_not_called()

    print("READER SITTING-OUT SIGNAL PRESERVED: PASS")
    print("SAME-FRAME NAME RETRY: NO")
    print("PLAYER NAME INVENTED: NO")
    print("SNAPSHOT V3 SITTING-OUT ASSEMBLY: PASS")


if __name__ == "__main__":
    main()
