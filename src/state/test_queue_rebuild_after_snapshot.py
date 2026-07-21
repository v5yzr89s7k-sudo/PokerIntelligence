from src.state.canonical_hand import CanonicalHand

hand = CanonicalHand().start_hand(
    hand_id="late-snapshot",
    players=[],
    hero_cards=["As", "Kd"],
    hero_position="unknown",
    positions={},
    started_ts=100.0,
)

assert hand.players_to_act == []

hand.update_table_snapshot(
    players=[
        {"seat":"seat_top","name":"UTG","stack_bb":40,"is_active":True},
        {"seat":"seat_upper_right","name":"HJ","stack_bb":40,"is_active":True},
        {"seat":"hero","name":"Hero","stack_bb":40,"is_hero":True,"is_active":True},
    ],
    hero_position="CO",
    positions={
        "seat_top":"UTG",
        "seat_upper_right":"HJ",
        "hero":"CO",
    },
)

assert hand.players_to_act == [
    "seat_top",
    "seat_upper_right",
    "hero",
]

print("Late snapshot queue rebuild regression passed.")
