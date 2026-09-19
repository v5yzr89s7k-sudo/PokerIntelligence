from pathlib import Path

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)
from src.v017.pixel_lab.acr_seat_mapper import (
    map_acr_seats,
    mapped_dealer_seat,
    mapped_players,
    mapped_positions,
)


ROOT = Path(__file__).resolve().parents[3]

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)

HAND_ID = "2826874674"


def main():
    hand = next(
        hand
        for _, hand in parse_corpus(
            CORPUS
        )
        if hand.hand_id == HAND_ID
    )

    first = map_acr_seats(hand)
    second = map_acr_seats(hand)
    third = map_acr_seats(hand)

    assert first == second == third

    print(
        "ACR -> physical =",
        first,
    )

    players = mapped_players(hand)

    print()
    print("PLAYERS:")

    for row in players:
        print(
            row["acr_seat_number"],
            row["name"],
            "->",
            row["seat"],
            "stack_bb=",
            row["stack_bb"],
            "HERO"
            if row["is_hero"]
            else "",
        )

    hero = next(
        row
        for row in players
        if row["is_hero"]
    )

    assert hero["acr_seat_number"] == 8
    assert hero["seat"] == "hero"

    dealer = mapped_dealer_seat(hand)

    print()
    print("dealer =", dealer)

    positions = mapped_positions(hand)

    print(
        "positions =",
        positions,
    )

    # Truth from the ACR action log:
    # seat 3 BTN
    # seat 4 SB
    # seat 5 BB
    assert positions[
        first[3]
    ] == "BTN"

    assert positions[
        first[4]
    ] == "SB"

    assert positions[
        first[5]
    ] == "BB"

    # The first voluntary actor is ACR seat 6 FERITIN,
    # therefore UTG six-handed.
    feritin = next(
        row
        for row in players
        if row["name"] == "FERITIN"
    )

    assert positions[
        feritin["seat"]
    ] == "UTG"

    # Six-handed order is:
    # BTN, SB, BB, UTG, HJ, CO.
    #
    # ACR seat 8 Hero acts after seat 7 HJ and before
    # the button, therefore Hero is CO.
    assert positions["hero"] == "CO"

    assert len(players) == 6

    print()
    print(
        "V0.17 PIXEL LAB ACR SEAT "
        "MAPPING: PASS"
    )


if __name__ == "__main__":
    main()
