from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker
from src.observer.action_inference_engine import (
    InferredAction,
    BET_OR_RAISE,
)

hand = CanonicalHand().start_hand(
    hand_id="ordering",
    players=[
        {"seat":"seat_top","name":"UTG","stack_bb":40},
        {"seat":"hero","name":"Hero","stack_bb":40,"is_hero":True},
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
        measurements={
            "stack_change":{
                "delta_bb":2.5
            }
        },
    )
)

state = tracker.commitment_tracker._state("PREFLOP")

assert state.last_aggressor == hand.last_aggressor_seat
assert state.current_price == hand.current_bet_bb
assert state.betting_open == tracker.has_open_bet

print("StreetCommitmentTracker ordering regression passed.")
