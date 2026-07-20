from src.state.canonical_hand import CanonicalHand


players = [
    {
        "seat": "seat_mid_left",
        "name": "Alice",
        "stack_bb": 40.0,
        "is_active": True,
    },
    {
        "seat": "hero",
        "name": "Hero",
        "stack_bb": 30.0,
        "is_hero": True,
        "is_active": True,
    },
]

positions = {
    "seat_mid_left": "BTN",
    "hero": "BB",
}

hand = CanonicalHand().start_hand(
    hand_id="street-summary-test",
    players=players,
    hero_cards=["As", "Kd"],
    hero_position="BB",
    positions=positions,
    started_ts=100.0,
)

hand.add_action(
    "seat_mid_left",
    "POST_SMALL_BLIND",
    amount_bb=0.5,
    ts=100.0,
)

hand.add_action(
    "hero",
    "POST_BIG_BLIND",
    amount_bb=1.0,
    ts=100.0,
)

hand.add_action(
    "seat_mid_left",
    "CALL",
    amount_bb=0.5,
    ts=101.0,
)

preflop = hand.street_summaries["PREFLOP"]

assert preflop.starting_pot_bb == 0.0
assert preflop.ending_pot_bb == 2.0
assert preflop.started_ts == 100.0
assert preflop.ended_ts is None

hand.set_board(
    ["Ah", "7c", "2d"],
    ts=102.0,
)

preflop = hand.street_summaries["PREFLOP"]
flop = hand.street_summaries["FLOP"]

assert preflop.ending_pot_bb == 2.0
assert preflop.ended_ts == 102.0

assert flop.starting_pot_bb == 2.0
assert flop.ending_pot_bb == 2.0
assert flop.started_ts == 102.0
assert flop.ended_ts is None

hand.add_action(
    "hero",
    "CHECK",
    ts=103.0,
)

hand.add_action(
    "seat_mid_left",
    "BET",
    amount_bb=1.5,
    ts=104.0,
)

assert hand.street_summaries["FLOP"].ending_pot_bb == 3.5

hand.set_board(
    ["Ah", "7c", "2d", "Ks"],
    ts=105.0,
)

flop = hand.street_summaries["FLOP"]
turn = hand.street_summaries["TURN"]

assert flop.ending_pot_bb == 3.5
assert flop.ended_ts == 105.0

assert turn.starting_pot_bb == 3.5
assert turn.ending_pot_bb == 3.5
assert turn.started_ts == 105.0

hand.finish(
    "Hero folded on turn",
    ended_ts=106.0,
)

assert hand.street_summaries["TURN"].ending_pot_bb == 3.5
assert hand.street_summaries["TURN"].ended_ts == 106.0

restored = CanonicalHand.from_dict(hand.to_dict())

assert restored.street_summaries["PREFLOP"].ending_pot_bb == 2.0
assert restored.street_summaries["FLOP"].starting_pot_bb == 2.0
assert restored.street_summaries["FLOP"].ending_pot_bb == 3.5
assert restored.street_summaries["TURN"].starting_pot_bb == 3.5
assert restored.street_summaries["TURN"].ended_ts == 106.0

print("StreetSummary lifecycle regression passed.")
