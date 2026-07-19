from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker
from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
)

hand = CanonicalHand().start_hand(
    hand_id="sync",
    players=[
        {"seat":"seat_top","name":"UTG","stack_bb":30},
        {"seat":"hero","name":"Hero","stack_bb":30,"is_hero":True},
    ],
    hero_cards=["As","Kd"],
    hero_position="BB",
    positions={
        "seat_top":"UTG",
        "hero":"BB",
    },
)

tracker = BettingRoundTracker(hand)

tracker.ingest(
    InferredAction(
        episode_id=1,
        seat="seat_top",
        street="PREFLOP",
        action=BET_OR_RAISE,
        confidence=0.9,
        evidence=[],
        reason="test",
        measurements={},
    )
)

state = tracker.commitment_tracker._state("PREFLOP")

assert "seat_top" in state.acted
assert state.pending_to_act == hand.players_to_act

print("StreetCommitmentTracker sync regression passed.")
