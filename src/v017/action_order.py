"""
Canonical V0.17 poker action ordering.

This module owns position-derived betting order only.
It contains no perception, simulator truth, or hand-specific state.
"""


def build_action_order(positions):
    preflop_order = [
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
        "BTN",
        "SB",
        "BB",
    ]

    rank = {
        position: index
        for index, position
        in enumerate(preflop_order)
    }

    return sorted(
        positions,
        key=lambda seat: (
            rank.get(
                positions.get(seat),
                999,
            ),
            seat,
        ),
    )


def postflop_action_order(observer):
    position_order = [
        "SB",
        "BB",
        "UTG",
        "UTG+1",
        "UTG+2",
        "LJ",
        "HJ",
        "CO",
        "BTN",
    ]

    rank = {
        position: index
        for index, position
        in enumerate(position_order)
    }

    seats = [
        seat
        for seat, player
        in observer.hand.players.items()
        if (
            player.dealt_in
            and not player.folded
        )
    ]

    return sorted(
        seats,
        key=lambda seat: (
            rank.get(
                observer.hand.players[
                    seat
                ].position,
                999,
            ),
            seat,
        ),
    )
