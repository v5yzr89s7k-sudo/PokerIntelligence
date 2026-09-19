"""
Private Pixel Lab ACR seat -> physical geometry mapping.

ACR numbered seats describe fixed table chairs.
Poker Intelligence geometry describes the same clockwise physical ring
with Hero normalized to the bottom-center `hero` slot.

Generator/comparator side only.
"""

from src.api.position_engine import (
    SEAT_ORDER,
    assign_positions,
)


def map_acr_seats(
    hand,
):
    assert hand.hero_name, (
        hand.hand_id,
        "missing Hero",
    )

    hero_player = next(
        (
            player
            for player in hand.players
            if player.name == hand.hero_name
        ),
        None,
    )

    assert hero_player is not None, (
        hand.hand_id,
        hand.hero_name,
    )

    # ACR 8-max physical chairs are numbered 1..8.
    acr_ring = tuple(range(1, 9))

    hero_acr = int(
        hero_player.seat_number
    )

    assert hero_acr in acr_ring

    physical_ring = tuple(SEAT_ORDER)

    assert len(physical_ring) == 8
    assert "hero" in physical_ring

    # Rotate the ACR ring and physical ring so both Hero anchors
    # occupy index zero, then pair clockwise.
    acr_index = acr_ring.index(hero_acr)
    acr_from_hero = (
        acr_ring[acr_index:]
        + acr_ring[:acr_index]
    )

    physical_index = physical_ring.index(
        "hero"
    )
    physical_from_hero = (
        physical_ring[physical_index:]
        + physical_ring[:physical_index]
    )

    full_map = dict(
        zip(
            acr_from_hero,
            physical_from_hero,
        )
    )

    occupied_numbers = {
        int(player.seat_number)
        for player in hand.players
        if not player.sitting_out
    }

    occupied_map = {
        number: full_map[number]
        for number in occupied_numbers
    }

    assert (
        occupied_map[hero_acr]
        == "hero"
    )

    assert len(
        set(occupied_map.values())
    ) == len(occupied_map)

    return occupied_map


def mapped_players(
    hand,
):
    seat_map = map_acr_seats(hand)

    return tuple(
        {
            "seat": seat_map[
                int(player.seat_number)
            ],
            "name": player.name,
            "stack_bb": (
                float(player.starting_stack)
                / float(hand.big_blind)
            ),
            "acr_seat_number":
                int(player.seat_number),
            "is_hero": (
                player.name
                == hand.hero_name
            ),
        }
        for player in hand.players
        if not player.sitting_out
    )


def mapped_dealer_seat(
    hand,
):
    seat_map = map_acr_seats(hand)

    button = int(hand.button_seat)

    # For this first acceptance hand the button is occupied.
    assert button in seat_map, (
        hand.hand_id,
        "dead button not yet supported by Pixel Lab mapper",
        button,
    )

    return seat_map[button]


def mapped_positions(
    hand,
):
    players = mapped_players(hand)
    dealer = mapped_dealer_seat(hand)

    return assign_positions(
        players,
        dealer,
        preserve_physical_slots=False,
    )
