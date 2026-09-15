from copy import deepcopy
from pathlib import Path
import tempfile

from src.v017.current_hand_renderer import (
    render_current_hand,
    write_current_hand,
)
from src.v017.july22_complete_hand import (
    build_complete_july22_hand,
)


EXPECTED_STREET_ACTIONS = {
    "PREFLOP": [
        "SB (poker5068) posts small blind 0.5 BB",
        "BB (Birkam) posts big blind 1 BB",
        "LJ (Slayer1950) folds",
        "HJ (Twib101) folds",
        "CO (Pablopg) folds",
        "BTN (AllinMatt31) raises to 2 BB",
        "SB (poker5068) calls 1.5 BB",
        "BB (Birkam) calls 1 BB",
    ],
    "FLOP": [
        "SB (poker5068) checks",
        "BB (Birkam) bets 3.37 BB",
        "BTN (AllinMatt31) folds",
        "SB (poker5068) calls 3.37 BB",
    ],
    "TURN": [
        "SB (poker5068) checks",
        "BB (Birkam) checks",
    ],
    "RIVER": [
        "SB (poker5068) checks",
        "BB (Birkam) bets 6.75 BB",
        "SB (poker5068) folds",
    ],
}


def snapshot(hand):
    return {
        "street": hand.street,
        "price": hand.current_price_bb,
        "pending": deepcopy(
            hand.pending_to_act
        ),
        "hero_cards": deepcopy(
            hand.hero_cards
        ),
        "board": deepcopy(
            hand.board
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

    before = snapshot(hand)

    text = render_current_hand(
        hand,
        started="2026-07-22 15:21:55",
        hand_id="july22-reference",
    )

    after = snapshot(hand)

    assert before == after

    print(text)

    # --------------------------------------------------------
    # Header / roster / cards.
    # --------------------------------------------------------

    assert "CURRENT HAND" in text
    assert "TABLE — 7 players seated" in text
    assert "HAND — 6 players dealt" in text
    assert "Fartsenia" in text
    assert "[NOT DEALT]" in text

    assert (
        "Hero Position: SB"
        in text
    )

    assert (
        "Hero Cards: Qd Ah"
        in text
    )

    for name in (
        "Birkam",
        "AllinMatt31",
        "Pablopg",
        "Twib101",
        "Slayer1950",
        "poker5068",
        "Fartsenia",
    ):
        assert name in text

    # --------------------------------------------------------
    # Objective board.
    # --------------------------------------------------------

    assert "FLOP: Jd 9s Tc" in text
    assert "TURN: 9h" in text
    assert "RIVER: 7h" in text

    # --------------------------------------------------------
    # Exact authoritative action presentation.
    # --------------------------------------------------------

    street_headers = {
        "PREFLOP": "PREFLOP",
        "FLOP": "FLOP: Jd 9s Tc",
        "TURN": "TURN: 9h",
        "RIVER": "RIVER: 7h",
    }

    street_order = [
        "PREFLOP",
        "FLOP",
        "TURN",
        "RIVER",
    ]

    for index, street in enumerate(
        street_order
    ):
        header = street_headers[
            street
        ]

        start = text.index(
            header
        )

        if index + 1 < len(
            street_order
        ):
            next_header = street_headers[
                street_order[index + 1]
            ]

            end = text.index(
                next_header,
                start + len(header),
            )
        else:
            end = text.index(
                "STATUS",
                start + len(header),
            )

        section = text[
            start:end
        ]

        expected = (
            EXPECTED_STREET_ACTIONS[
                street
            ]
        )

        for line in expected:
            assert section.count(
                line
            ) == 1, (
                street,
                line,
                section.count(line),
            )

    # No old semantic vocabulary may leak into product output.
    forbidden = (
        "commits chips",
        "BET_OR_RAISE",
        "CALL_OR_RAISE",
        "provisional",
        "chronology_pending",
        "inferred",
    )

    for term in forbidden:
        assert term not in text

    # No pot values yet: pot state has not been given authority
    # in v0.17.
    assert "Pot:" not in text
    assert "POT" not in text

    # --------------------------------------------------------
    # Writer must produce exactly the pure renderer output.
    # --------------------------------------------------------

    with tempfile.TemporaryDirectory() as td:
        path = (
            Path(td)
            / "current_hand.txt"
        )

        written = write_current_hand(
            hand,
            path,
            started="2026-07-22 15:21:55",
            hand_id="july22-reference",
        )

        assert written == text
        assert path.read_text() == text

    assert snapshot(hand) == before

    print(
        "V0.17 JULY22 CURRENT_HAND RENDERER: PASS"
    )


if __name__ == "__main__":
    main()
