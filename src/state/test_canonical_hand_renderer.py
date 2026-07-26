from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_renderer import render_canonical_hand


players = [
    {
        "seat": "seat_mid_left",
        "name": "Alice",
        "stack_bb": 42.0,
        "is_hero": False,
        "is_active": True,
    },
    {
        "seat": "seat_lower_right",
        "name": "Bob",
        "stack_bb": 31.5,
        "is_hero": False,
        "is_active": True,
    },
    {
        "seat": "hero",
        "name": "Hero",
        "stack_bb": 28.0,
        "is_hero": True,
        "is_active": True,
    },
]

positions = {
    "seat_mid_left": "CO",
    "seat_lower_right": "BTN",
    "hero": "BB",
}

hand = CanonicalHand().start_hand(
    hand_id="test-hand-1",
    players=players,
    hero_cards=["As", "Kd"],
    hero_position="BB",
    positions=positions,
    started_ts=100.0,
)

hand.add_action("seat_mid_left", "FOLD", ts=101.0)
hand.add_action(
    "seat_lower_right",
    "RAISE",
    raise_to_bb=2.2,
    ts=102.0,
)
hand.add_action(
    "hero",
    "CALL",
    amount_bb=1.2,
    ts=103.0,
)

hand.set_board(["Ah", "7c", "2d"])
hand.add_action("hero", "CHECK", ts=104.0)
hand.add_action(
    "seat_lower_right",
    "BET",
    amount_bb=2.5,
    ts=105.0,
)
hand.add_action(
    "hero",
    "CALL",
    amount_bb=2.5,
    ts=106.0,
)

hand.set_board(["Ah", "7c", "2d", "Ks"])
hand.add_action("hero", "CHECK", ts=107.0)
hand.add_action("seat_lower_right", "CHECK", ts=108.0)

hand.set_board(["Ah", "7c", "2d", "Ks", "3h"])
hand.add_action("hero", "CHECK", ts=109.0)
hand.add_action("seat_lower_right", "CHECK", ts=110.0)

hand.add_showdown("hero", ["As", "Kd"], ts=110.5)
hand.add_showdown("seat_lower_right", ["Ac", "Qc"], ts=110.6)

assert hand.street_summaries["RIVER"].ended_ts == 110.5
hand.add_pot_result("main pot", 14.4, ["hero"])
hand.finish("Hero wins main pot", ended_ts=111.0)

text = render_canonical_hand(hand)

assert "TABLE — 3 players" in text
assert "Starting Pot: 0 BB" in text
assert "Ending Pot: 3.4 BB" in text
assert "Starting Pot: 3.4 BB" in text
assert "Ending Pot: 8.4 BB" in text

assert "CO (Alice) folds" in text
assert "BTN (Bob) opens to 2.2 BB" in text
assert "BB (Hero) calls 1.2 BB" in text
assert "FLOP: Ah 7c 2d" in text
assert "BTN (Bob) bets 2.5 BB" in text
assert "TURN: Ks" in text
assert "RIVER: 3h" in text
assert "BB (Hero) shows As Kd" in text
assert "Main Pot: 14.4 BB — Winner: BB" in text
assert "Hero wins main pot" in text

print(text)
print("CanonicalHand renderer smoke test passed.")


def test_preflop_raise_language():
    language_hand = CanonicalHand().start_hand(
        hand_id="raise-language",
        players=[
            {
                "seat": "seat_top",
                "name": "Alice",
                "stack_bb": 50,
            },
            {
                "seat": "seat_upper_right",
                "name": "Bob",
                "stack_bb": 50,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={
            "seat_top": "CO",
            "seat_upper_right": "SB",
            "hero": "BTN",
        },
        started_ts=200.0,
    )

    language_hand.add_action(
        "seat_top",
        "RAISE",
        raise_to_bb=2.5,
        ts=201.0,
    )
    language_hand.add_action(
        "hero",
        "RAISE",
        raise_to_bb=8.0,
        ts=202.0,
    )
    language_hand.add_action(
        "seat_upper_right",
        "RAISE",
        raise_to_bb=22.0,
        ts=203.0,
    )

    rendered = render_canonical_hand(language_hand)

    assert "CO (Alice) opens to 2.5 BB" in rendered
    assert "BTN (Hero) 3-bets to 8 BB" in rendered
    assert "SB (Bob) 4-bets to 22 BB" in rendered
