from src.state.canonical_hand import CanonicalHand


def make_eight_handed_hand():
    positions = {
        "seat_top": "UTG",
        "seat_upper_right": "UTG+1",
        "seat_mid_right": "LJ",
        "seat_lower_right": "HJ",
        "hero": "CO",
        "seat_lower_left": "BTN",
        "seat_mid_left": "SB",
        "seat_upper_left": "BB",
    }

    players = [
        {
            "seat": seat,
            "name": position,
            "stack_bb": 40,
            "is_hero": seat == "hero",
        }
        for seat, position in positions.items()
    ]

    return CanonicalHand().start_hand(
        hand_id="queue-eight-handed",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="CO",
        positions=positions,
        started_ts=1000.0,
    )


def test_eight_handed_preflop_order():
    hand = make_eight_handed_hand()

    assert hand.players_to_act == [
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
    ]


def test_eight_handed_postflop_order():
    hand = make_eight_handed_hand()

    hand.set_board(["Ah", "7c", "2d"])

    assert hand.players_to_act == [
        "seat_mid_left",
        "seat_upper_left",
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
    ]


def test_folded_and_all_in_players_are_excluded():
    hand = make_eight_handed_hand()

    hand.players["seat_mid_left"].folded = True
    hand.players["seat_mid_left"].active = False
    hand.players["seat_upper_right"].all_in = True

    hand.set_board(["Ah", "7c", "2d"])

    assert "seat_mid_left" not in hand.players_to_act
    assert "seat_upper_right" not in hand.players_to_act

    assert hand.players_to_act == [
        "seat_upper_left",
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
    ]


def test_heads_up_order():
    positions = {
        "hero": "BTN",
        "seat_top": "BB",
    }

    hand = CanonicalHand().start_hand(
        hand_id="queue-heads-up",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 30,
                "is_hero": True,
            },
            {
                "seat": "seat_top",
                "name": "Villain",
                "stack_bb": 30,
            },
        ],
        hero_cards=["Qs", "Jh"],
        hero_position="BTN",
        positions=positions,
        started_ts=1000.0,
    )

    assert hand.players_to_act == [
        "hero",
        "seat_top",
    ]

    hand.set_board(["9s", "4h", "2c"])

    assert hand.players_to_act == [
        "seat_top",
        "hero",
    ]


if __name__ == "__main__":
    test_eight_handed_preflop_order()
    test_eight_handed_postflop_order()
    test_folded_and_all_in_players_are_excluded()
    test_heads_up_order()
    test_showdown_and_completion_clear_queue()

    print("players_to_act initialization regression tests passed.")


def test_showdown_and_completion_clear_queue():
    hand = make_eight_handed_hand()

    hand.set_board(["Ah", "7c", "2d"])
    assert hand.players_to_act

    hand.set_showdown([])
    assert hand.current_street == "SHOWDOWN"
    assert hand.players_to_act == []

    hand.close_hand(result="test complete")
    assert hand.current_street == "COMPLETE"
    assert hand.players_to_act == []
