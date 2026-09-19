from collections import Counter
from pathlib import Path

from src.v017.pixel_lab.acr_hand_parser import (
    parse_corpus,
)


ROOT = Path(__file__).resolve().parents[3]

CORPUS = (
    ROOT
    / "runtime/pixel_lab/acr_hand_histories"
)


def main():
    rows = parse_corpus(CORPUS)

    assert rows, "empty ACR corpus"

    ids = [
        hand.hand_id
        for _, hand in rows
    ]

    assert len(ids) == len(set(ids)), (
        "duplicate hand IDs in corpus"
    )

    player_counts = Counter()
    street_counts = Counter()
    action_counts = Counter()

    hero_card_hands = 0
    complete_player_maps = 0

    for path, hand in rows:
        assert hand.players
        assert hand.big_blind > 0
        assert hand.small_blind > 0
        assert hand.button_seat > 0

        names = {
            player.name
            for player in hand.players
        }

        assert len(names) == len(
            hand.players
        )

        assert all(
            action.actor in names
            for action in hand.actions
        ), (
            path.name,
            hand.hand_id,
            tuple(
                action
                for action in hand.actions
                if action.actor not in names
            ),
        )

        player_counts[
            len(hand.players)
        ] += 1

        if hand.hero_cards:
            hero_card_hands += 1
            assert len(
                hand.hero_cards
            ) == 2

        if hand.flop:
            street_counts["FLOP"] += 1
            assert len(hand.flop) == 3

        if hand.turn:
            street_counts["TURN"] += 1

        if hand.river:
            street_counts["RIVER"] += 1

        for action in hand.actions:
            action_counts[
                action.action
            ] += 1

        complete_player_maps += 1

    print(
        "files =",
        len(
            {
                path
                for path, _ in rows
            }
        ),
    )

    print(
        "hands =",
        len(rows),
    )

    print(
        "player counts =",
        dict(
            sorted(
                player_counts.items()
            )
        ),
    )

    print(
        "street counts =",
        dict(street_counts),
    )

    print(
        "action counts =",
        dict(
            sorted(
                action_counts.items()
            )
        ),
    )

    print(
        "hero-card hands =",
        hero_card_hands,
    )

    print(
        "complete player maps =",
        complete_player_maps,
    )

    print()
    print("===== SAMPLE HANDS =====")

    for path, hand in rows[:8]:
        print()
        print(
            path.name,
            hand.hand_id,
        )
        print(
            " players=",
            len(hand.players),
            "button=",
            hand.button_seat,
            "blinds=",
            (
                hand.small_blind,
                hand.big_blind,
            ),
        )
        print(
            " hero=",
            hand.hero_name,
            hand.hero_cards,
        )
        print(
            " board=",
            hand.flop,
            hand.turn,
            hand.river,
        )
        print(
            " actions=",
            len(hand.actions),
        )
        print(
            " winners=",
            hand.winners,
        )

    print()
    print(
        "V0.17 PIXEL LAB ACR "
        "HAND PARSER: PASS"
    )


if __name__ == "__main__":
    main()
