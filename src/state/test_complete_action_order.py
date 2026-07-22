from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand(street="PREFLOP"):
    players = [
        {"seat": "seat_top", "name": "P1", "stack_bb": 50},
        {"seat": "seat_upper_right", "name": "P2", "stack_bb": 50},
        {"seat": "hero", "name": "Hero", "stack_bb": 50},
    ]
    positions = {
        "seat_top": "UTG",
        "seat_upper_right": "HJ",
        "hero": "BTN",
    }

    hand = CanonicalHand().start_hand(
        hand_id=f"test-{street.lower()}",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions=positions,
    )
    hand.dealt_in_seats = list(positions)

    if street == "FLOP":
        hand.set_board(["2c", "7d", "Jh"], ts=1.0)

    hand.players_to_act = ["seat_top", "seat_upper_right", "hero"]
    return hand


def test_preflop_skipped_players_fold():
    hand = make_hand()
    hand.current_bet_bb = 1.0
    tracker = BettingRoundTracker(hand)

    tracker.ingest({
        "episode_id": 1,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {"stack_change": {"delta_bb": 2.5}},
        "evidence": ["stack_changed", "bet_region_occupied"],
        "ts": 2.0,
    })

    actions = [(a.seat, a.action) for a in hand.actions]
    assert actions == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", "FOLD"),
        ("hero", "RAISE"),
    ]


def test_postflop_skipped_players_check_without_bet():
    hand = make_hand("FLOP")
    hand.current_bet_bb = 0.0
    tracker = BettingRoundTracker(hand)

    tracker.ingest({
        "episode_id": 2,
        "seat": "hero",
        "street": "FLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {"stack_change": {"delta_bb": 3.0}},
        "evidence": ["stack_changed", "bet_region_occupied"],
        "ts": 2.0,
    })

    actions = [
        (a.seat, a.action)
        for a in hand.actions
        if a.street == "FLOP"
    ]
    assert actions == [
        ("seat_top", "CHECK"),
        ("seat_upper_right", "CHECK"),
        ("hero", "BET"),
    ]


def test_skipped_players_fold_facing_bet():
    hand = make_hand("FLOP")
    hand.current_bet_bb = 3.0
    hand.last_aggressor_seat = "hero"

    tracker = BettingRoundTracker(hand)
    tracker.has_open_bet = True

    tracker.ingest({
        "episode_id": 3,
        "seat": "hero",
        "street": "FLOP",
        "action": "CALL",
        "confidence": 0.90,
        "measurements": {"stack_change": {"delta_bb": 3.0}},
        "evidence": ["stack_changed", "pot_changed"],
        "ts": 2.0,
    })

    actions = [
        (a.seat, a.action)
        for a in hand.actions
        if a.street == "FLOP"
    ]
    assert actions == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", "FOLD"),
        ("hero", "CALL"),
    ]


if __name__ == "__main__":
    test_preflop_skipped_players_fold()
    test_postflop_skipped_players_check_without_bet()
    test_skipped_players_fold_facing_bet()
    print("complete action-order regressions passed")
