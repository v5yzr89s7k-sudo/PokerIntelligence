from copy import deepcopy

from src.v017.hand_projection import (
    project_hand,
)
from src.v017.july22_complete_hand import (
    HERO_CARDS,
    RIVER_BOARD,
    build_complete_july22_hand,
)


EXPECTED_ACTIONS = [
    ("PREFLOP", "SB",  "POST_SMALL_BLIND", 0.5, None),
    ("PREFLOP", "BB",  "POST_BIG_BLIND",   1.0, None),
    ("PREFLOP", "LJ",  "FOLD",             None, None),
    ("PREFLOP", "HJ",  "FOLD",             None, None),
    ("PREFLOP", "CO",  "FOLD",             None, None),
    ("PREFLOP", "BTN", "RAISE",            None, 2.0),
    ("PREFLOP", "SB",  "CALL",             1.5, None),
    ("PREFLOP", "BB",  "CALL",             1.0, None),

    ("FLOP",    "SB",  "CHECK",             None, None),
    ("FLOP",    "BB",  "BET",               3.37, None),
    ("FLOP",    "BTN", "FOLD",              None, None),
    ("FLOP",    "SB",  "CALL",              3.37, None),

    ("TURN",    "SB",  "CHECK",             None, None),
    ("TURN",    "BB",  "CHECK",             None, None),

    ("RIVER",   "SB",  "CHECK",             None, None),
    ("RIVER",   "BB",  "BET",               6.75, None),
    ("RIVER",   "SB",  "FOLD",              None, None),
]


def state_snapshot(hand):
    return {
        "street": hand.street,
        "next_actor": hand.next_actor,
        "price": hand.current_price_bb,
        "hero_cards": deepcopy(
            hand.hero_cards
        ),
        "board": deepcopy(
            hand.board
        ),
        "pending": deepcopy(
            hand.pending_to_act
        ),
        "actions": deepcopy(
            hand.semantic_actions()
        ),
        "players": {
            seat: {
                "folded": player.folded,
                "commitment": (
                    player.street_commitment_bb
                ),
                "starting_stack": (
                    player.starting_stack_bb
                ),
            }
            for seat, player
            in hand.players.items()
        },
    }


def main():
    hand = build_complete_july22_hand()

    assert hand.hero_cards == HERO_CARDS
    assert hand.board == RIVER_BOARD
    assert hand.street == "RIVER"
    assert hand.next_actor is None
    assert len(hand.actions) == 17

    observed = [
        (
            action["street"],
            action["position"],
            action["action"],
            action["amount_bb"],
            action["raise_to_bb"],
        )
        for action in hand.semantic_actions()
    ]

    assert observed == EXPECTED_ACTIONS, observed

    before = state_snapshot(hand)

    projection = project_hand(
        hand
    )

    after = state_snapshot(hand)

    # Presentation cannot mutate authority.
    assert before == after

    assert projection[
        "hero_cards"
    ] == HERO_CARDS

    assert projection[
        "board"
    ] == RIVER_BOARD

    assert projection[
        "actions"
    ] == hand.semantic_actions()

    print("===== JULY22 AUTHORITATIVE HAND =====")
    print("Hero Cards:", " ".join(HERO_CARDS))
    print(
        "Board:",
        " ".join(RIVER_BOARD),
    )

    print()
    print("===== 17 AUTHORITATIVE ACTIONS =====")

    for line in projection[
        "formatted_actions"
    ]:
        print(line)

    print()
    print(
        "V0.17 JULY22 COMPLETE HAND: PASS"
    )


if __name__ == "__main__":
    main()
