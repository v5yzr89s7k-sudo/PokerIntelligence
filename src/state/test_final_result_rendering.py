from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_renderer import render_canonical_hand


def main():
    hand = CanonicalHand().start_hand(
        hand_id="result-render-test",
        players=[
            {
                "seat": "hero",
                "name": "poker5068",
                "stack_bb": 83.20,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_lower_right",
                "name": "warreneen",
                "stack_bb": 75.08,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["8s", "4h"],
        hero_position="UTG+1",
        positions={
            "hero": "UTG+1",
            "seat_lower_right": "UTG",
        },
        started_ts=1.0,
    )

    hand.add_pot_result(
        pot_type="final_pot",
        amount_bb=117.33,
        winners=["seat_lower_right"],
    )

    hand.finish(
        result="Board cleared after river",
        ended_ts=2.0,
    )

    text = render_canonical_hand(hand)

    assert "RESULT" in text, text
    assert "Winner: UTG (warreneen)" in text, text
    assert "Final Pot: 117.33 BB" in text, text

    print(text)

    print(
        "PASS final result rendering: "
        "winner position/name and final pot are explicit"
    )


if __name__ == "__main__":
    main()
