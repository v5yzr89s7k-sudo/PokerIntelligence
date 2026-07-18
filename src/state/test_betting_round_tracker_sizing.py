from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker

hand = CanonicalHand()
hand.current_street = "PREFLOP"

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
