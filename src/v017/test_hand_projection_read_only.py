from copy import deepcopy

from src.v017.hand_projection import (
    project_hand,
)
from src.v017.test_july22_river_chronology import (
    build_through_turn,
)


def snapshot(hand):
    return {
        "street": hand.street,
        "price": hand.current_price_bb,
        "pending": list(hand.pending_to_act),
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
    hand = build_through_turn()

    before = snapshot(hand)

    projection = project_hand(hand)

    after = snapshot(hand)

    assert before == after

    assert (
        projection["actions"]
        == hand.semantic_actions()
    )

    assert len(
        projection["formatted_actions"]
    ) == len(hand.actions)

    forbidden = {
        "BET_OR_RAISE",
        "CALL_OR_RAISE",
        "COMMITMENT",
    }

    observed = {
        action["action"]
        for action in projection["actions"]
    }

    assert not (
        forbidden & observed
    )

    print("===== PRESENTATION SAMPLE =====")

    for line in projection[
        "formatted_actions"
    ]:
        print(line)

    print()
    print(
        "V0.17 READ-ONLY HAND "
        "PROJECTION: PASS"
    )


if __name__ == "__main__":
    main()
