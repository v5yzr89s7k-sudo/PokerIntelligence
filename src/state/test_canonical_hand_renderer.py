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

hand.add_showdown("hero", ["As", "Kd"])
hand.add_showdown("seat_lower_right", ["Ac", "Qc"])
hand.add_pot_result("main pot", 14.4, ["hero"])
hand.finish("Hero wins main pot", ended_ts=111.0)

text = render_canonical_hand(hand)

assert "TABLE — 3 players" in text
assert "CO (Alice) folds" in text
assert "BTN (Bob) raises to 2.2 BB" in text
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
