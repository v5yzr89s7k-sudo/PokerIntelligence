from src.state.canonical_hand import CanonicalHand


hand = CanonicalHand().start_hand(
    hand_id="fold-guard",
    players=[
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 50.0,
            "is_hero": True,
            "is_active": True,
        },
        {
            "seat": "seat_top",
            "name": "Villain",
            "stack_bb": 50.0,
            "is_hero": False,
            "is_active": True,
        },
    ],
    hero_cards=["8d", "6h"],
    hero_position="UTG",
    positions={
        "hero": "UTG",
        "seat_top": "CO",
    },
)

hand.add_action(
    seat="hero",
    action="FOLD",
    confidence=1.0,
)

assert hand.players["hero"].folded is True
assert hand.players["hero"].active is False

try:
    hand.add_action(
        seat="hero",
        action="BET",
        amount_bb=7.31,
        confidence=0.75,
    )
except ValueError as exc:
    assert "player_already_folded_or_inactive" in str(exc)
else:
    raise AssertionError("folded Hero was allowed to bet")

assert [
    action.action
    for action in hand.actions
    if action.seat == "hero"
] == ["FOLD"]

print("Folded-player action guard test passed.")
