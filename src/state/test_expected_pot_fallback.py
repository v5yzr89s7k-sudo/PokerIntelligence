from src.state.canonical_hand import CanonicalHand

hand = CanonicalHand()

players = [
    {
        "seat": "hero",
        "name": "Hero",
        "stack_bb": 100,
        "is_hero": True,
    },
    {
        "seat": "seat_lower_right",
        "name": "Villain",
        "stack_bb": 100,
    },
]

positions = {
    "hero": "BB",
    "seat_lower_right": "SB",
}

hand.start_hand(
    hand_id="test",
    players=players,
    hero_cards=["As","Kd"],
    hero_position="BB",
    positions=positions,
)

hand.add_action(
    "seat_lower_right",
    "POST_SMALL_BLIND",
    amount_bb=0.5,
)

hand.add_action(
    "hero",
    "POST_BIG_BLIND",
    amount_bb=1.0,
)

assert hand.expected_pot_bb == 1.5
assert hand.street_summaries["PREFLOP"].ending_pot_bb == 1.5

hand.set_board(["Ah","7c","2d"])

assert hand.street_summaries["FLOP"].starting_pot_bb == 1.5

print("expected pot fallback regression passed")
