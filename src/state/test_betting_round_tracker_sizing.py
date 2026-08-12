from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker

hand = CanonicalHand()
hand.current_street = "PREFLOP"
hand.current_bet_bb = 1.0

# Minimal generic player objects
class Player:
    def __init__(self, position, name, committed):
        self.position = position
        self.name = name
        self.folded = False
        self.active = True
        self.all_in = False
        self.committed_by_street = {"PREFLOP": committed}

hand.players = {
    "raiser": Player("P1", "Player1", 0.5),
    "caller": Player("P2", "Player2", 0.0),
}

tracker = BettingRoundTracker(hand)

# Existing commitment (0.5) + delta (14.5) = raise_to 15.0
raise_action = tracker.ingest({
    "episode_id": 1,
    "seat": "raiser",
    "street": "PREFLOP",
    "action": "BET_OR_RAISE",
    "measurements": {
        "stack_change": {
            "delta_bb": 14.5
        }
    }
})

assert raise_action is not None
assert raise_action.raise_to_bb == 15.0
assert raise_action.amount_bb is None

# CALL_OR_RAISE should preserve only the incremental amount
call_action = tracker.ingest({
    "episode_id": 2,
    "seat": "caller",
    "street": "PREFLOP",
    "action": "CALL_OR_RAISE",
    "measurements": {
        "stack_change": {
            "delta_bb": 12.0
        }
    }
})

assert call_action is not None
assert call_action.amount_bb == 12.0
assert call_action.raise_to_bb is None

print("BettingRoundTracker sizing regression test passed.")


# Regression: an ante is dead money and must not increase the live price
# comparison for a later voluntary action.
#
# Hero has already posted a 0.125 BB ante. A subsequent 1.0 BB stack
# decrease while facing a 1.0 BB live price is a CALL, not a raise to 1.125.
ante_hand = CanonicalHand().start_hand(
    hand_id="ante-sizing-regression",
    players=[
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 30.0,
            "is_hero": True,
        },
        {
            "seat": "big_blind",
            "name": "BigBlind",
            "stack_bb": 30.0,
        },
    ],
    hero_cards=["As", "Kd"],
    hero_position="BTN",
    positions={
        "hero": "BTN",
        "big_blind": "BB",
    },
    started_ts=1000.0,
)

ante_hand.add_action(
    seat="hero",
    action="POST_ANTE",
    amount_bb=0.125,
    confidence=1.0,
    source="test_hand_initialization",
)

ante_hand.add_action(
    seat="big_blind",
    action="POST_ANTE",
    amount_bb=0.125,
    confidence=1.0,
    source="test_hand_initialization",
)

ante_hand.add_action(
    seat="big_blind",
    action="POST_BIG_BLIND",
    amount_bb=1.0,
    confidence=1.0,
    source="test_hand_initialization",
)

ante_hand.current_bet_bb = 1.0

ante_tracker = BettingRoundTracker(ante_hand)

ante_call = ante_tracker.ingest({
    "episode_id": 1000,
    "seat": "hero",
    "street": "PREFLOP",
    "action": "CALL_OR_RAISE",
    "measurements": {
        "stack_change": {
            "delta_bb": 1.0,
        },
    },
})

assert ante_call is not None
assert ante_call.action == "CALL", (
    ante_call.action,
    ante_call.amount_bb,
    ante_call.raise_to_bb,
)
assert ante_call.amount_bb == 1.0
assert ante_call.raise_to_bb is None

assert (
    ante_hand.players["hero"]
    .committed_by_street["PREFLOP"]
    == 1.125
)

assert ante_hand.expected_pot_bb == 2.25

print(
    "Preflop ante stack-delta accounting regression test passed."
)
