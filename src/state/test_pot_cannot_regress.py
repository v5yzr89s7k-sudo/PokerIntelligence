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
        "seat": "villain",
        "name": "Villain",
        "stack_bb": 100,
    },
]

hand.start_hand(
    hand_id="pot-regression",
    players=players,
    hero_cards=["As", "Kd"],
    hero_position="BB",
    positions={
        "hero": "BB",
        "villain": "SB",
    },
)

hand.set_observed_pot(9.5)

hand.set_board(["8d", "8h", "As"])
hand.set_board(["8d", "8h", "As", "Jh"])
hand.set_board(["8d", "8h", "As", "Jh", "9c"])

river = hand.street_summaries["RIVER"]

assert river.starting_pot_bb == 9.5
assert river.ending_pot_bb == 9.5

# Simulate incomplete reconstructed river accounting.
hand.add_action(
    "villain",
    "BET",
    amount_bb=0.62,
)

river = hand.street_summaries["RIVER"]

assert hand.expected_pot_bb < 9.5
assert river.starting_pot_bb == 9.5
assert river.ending_pot_bb >= 9.5

print(
    "Pot regression invariant passed:",
    "starting=",
    river.starting_pot_bb,
    "expected=",
    hand.expected_pot_bb,
    "ending=",
    river.ending_pot_bb,
)
