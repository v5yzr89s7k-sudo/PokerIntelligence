from src.state.canonical_hand import CanonicalHand


def test_snapshot_seeds_missing_stack_baselines():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="snapshot-baseline-test",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": None,
                "is_hero": True,
            },
            {
                "seat": "seat_top",
                "name": "Villain",
                "stack_bb": None,
            },
        ],
        hero_cards=["Ac", "Kd"],
        hero_position="BB",
        positions={
            "hero": "BB",
            "seat_top": "BTN",
        },
    )

    hand.update_table_snapshot(
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 41.88,
                "is_hero": True,
            },
            {
                "seat": "seat_top",
                "name": "Villain",
                "stack_bb": 20.81,
            },
        ],
        hero_position="BB",
        positions={
            "hero": "BB",
            "seat_top": "BTN",
        },
        dealt_in_seats=["hero", "seat_top"],
    )

    hero = hand.players["hero"]
    villain = hand.players["seat_top"]

    assert hero.starting_stack_bb == 41.88
    assert hero.current_stack_bb == 41.88
    assert hero.last_confirmed_stack_bb == 41.88

    assert villain.starting_stack_bb == 20.81
    assert villain.current_stack_bb == 20.81
    assert villain.last_confirmed_stack_bb == 20.81

    result = hand.update_player_stack("hero", 40.88)

    assert result == {
        "seat": "hero",
        "previous_stack_bb": 41.88,
        "current_stack_bb": 40.88,
        "delta_bb": 1.0,
        "initialized": False,
    }


def test_snapshot_does_not_overwrite_existing_live_stack():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="snapshot-preserve-test",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 41.88,
                "is_hero": True,
            },
        ],
        hero_cards=["Ac", "Kd"],
        hero_position="BB",
        positions={"hero": "BB"},
    )

    first_update = hand.update_player_stack("hero", 40.88)
    assert first_update["delta_bb"] == 1.0

    hand.update_table_snapshot(
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 41.88,
                "is_hero": True,
            },
        ],
        hero_position="BB",
        positions={"hero": "BB"},
        dealt_in_seats=["hero"],
    )

    hero = hand.players["hero"]

    assert hero.starting_stack_bb == 41.88
    assert hero.current_stack_bb == 40.88
    assert hero.last_confirmed_stack_bb == 40.88
