"""
Objective card-observation normalization.

Converts equivalent card notation into the canonical product notation.
Does not infer card identity.
"""


def normalize_card(card):
    if card is None:
        raise ValueError(
            "card cannot be None"
        )

    value = str(card).strip()

    if len(value) < 2:
        raise ValueError(
            f"invalid card: {card!r}"
        )

    suit = value[-1].lower()
    rank = value[:-1].upper()

    if rank == "10":
        rank = "T"

    if rank not in {
        "2", "3", "4", "5", "6",
        "7", "8", "9",
        "T", "J", "Q", "K", "A",
    }:
        raise ValueError(
            f"invalid rank: {card!r}"
        )

    if suit not in {
        "c", "d", "h", "s",
    }:
        raise ValueError(
            f"invalid suit: {card!r}"
        )

    return rank + suit


def normalize_cards(cards):
    return [
        normalize_card(card)
        for card in cards
    ]


def board_after_from_transition(
    observation,
):
    board = (
        observation.get(
            "board_after"
        )
        or []
    )

    return normalize_cards(
        board
    )
