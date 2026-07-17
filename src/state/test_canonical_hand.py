from src.state.canonical_hand import CanonicalHand


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

hand.add_action(
    "hero",
    "CHECK",
    ts=104.0,
)
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
hand.add_pot_result("main", 14.4, ["hero"])
hand.finish("Hero wins main pot", ended_ts=111.0)

data = hand.to_dict()

assert data["hand_id"] == "test-hand-1"
assert data["hero_cards"] == ["As", "Kd"]
assert data["board"] == ["Ah", "7c", "2d", "Ks", "3h"]
assert len(data["actions"]) == 10
assert data["actions"][0]["action"] == "FOLD"
assert data["actions"][1]["raise_to_bb"] == 2.2
assert data["players"]["seat_mid_left"]["folded"] is True
assert data["players"]["hero"]["committed_by_street"]["PREFLOP"] == 1.2
assert data["last_aggressor_seat"] is None
assert data["closed"] is True
assert data["result"] == "Hero wins main pot"

print(data)
print()
print("CanonicalHand smoke test passed.")


def test_late_snapshot_refreshes_existing_action_labels():
    hand = CanonicalHand().start_hand(
        hand_id="late-snapshot",
        players=[],
        hero_cards=["As", "Kd"],
        hero_position="unknown",
        positions={},
        started_ts=1000.0,
    )

    action = hand.add_action(
        seat="seat_upper_right",
        action="BET",
        confidence=0.75,
    )

    assert action.position == "unknown"
    assert action.player_name == "seat_upper_right"

    hand.update_table_snapshot(
        players=[{
            "seat": "seat_upper_right",
            "name": "NOBI_B",
            "stack_bb": 65.67,
            "is_active": True,
        }],
        hero_position="SB",
        positions={"seat_upper_right": "HJ"},
    )

    assert action.position == "HJ"
    assert action.player_name == "NOBI_B"
