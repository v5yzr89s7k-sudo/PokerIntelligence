from src.state.betting_round_tracker import BettingRoundTracker
from src.state.canonical_hand import CanonicalHand


def make_hand(street="PREFLOP"):
    hand = CanonicalHand().start_hand(
        hand_id=f"cursor-{street.lower()}",
        players=[
            {"seat": "seat_top", "name": "P1", "stack_bb": 50},
            {
                "seat": "seat_upper_right",
                "name": "P2",
                "stack_bb": 50,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50,
                "is_hero": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={
            "seat_top": "UTG",
            "seat_upper_right": "HJ",
            "hero": "BTN",
        },
    )

    if street == "FLOP":
        hand.set_board(["2c", "7d", "Jh"], ts=1.0)

    hand.players_to_act = [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]

    return hand


def test_preflop_cursor_resolves_prior_seats_only():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    result = tracker.advance_to_observed_actor(
        "hero",
        ts=2.0,
    )

    assert [
        (action.seat, action.action)
        for action in result
    ] == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", "FOLD"),
    ]

    assert hand.players_to_act == ["hero"]

    assert not any(
        action.seat == "hero"
        for action in hand.actions
    )


def test_postflop_cursor_resolves_checks_only():
    hand = make_hand("FLOP")
    tracker = BettingRoundTracker(hand)

    result = tracker.advance_to_observed_actor(
        "hero",
        ts=2.0,
    )

    assert [
        (action.seat, action.action)
        for action in result
    ] == [
        ("seat_top", "CHECK"),
        ("seat_upper_right", "CHECK"),
    ]

    assert hand.players_to_act == ["hero"]


def test_blocked_gap_does_not_mutate_chronology():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    before = list(hand.players_to_act)

    result = tracker.advance_to_observed_actor(
        "hero",
        ts=2.0,
        blocked_seats={"seat_upper_right"},
    )

    assert result == []
    assert hand.players_to_act == before
    assert hand.actions == []

    assert not hand.players["seat_top"].folded
    assert not hand.players["seat_upper_right"].folded


def test_first_actor_is_noop():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    before = list(hand.players_to_act)

    result = tracker.advance_to_observed_actor(
        "seat_top",
        ts=2.0,
    )

    assert result == []
    assert hand.players_to_act == before
    assert hand.actions == []


if __name__ == "__main__":
    test_preflop_cursor_resolves_prior_seats_only()
    test_postflop_cursor_resolves_checks_only()
    test_blocked_gap_does_not_mutate_chronology()
    test_first_actor_is_noop()

    print("PASS action cursor advance")
