from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)


def make_tracker():
    players = [
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 10.28,
            "is_hero": True,
        },
        {
            "seat": "bb",
            "name": "BB",
            "stack_bb": 47.57,
        },
        {
            "seat": "btn",
            "name": "BTN",
            "stack_bb": 56.55,
        },
    ]

    positions = {
        "hero": "SB",
        "bb": "BB",
        "btn": "BTN",
    }

    hand = CanonicalHand().start_hand(
        hand_id="provisional-bet-block",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions=positions,
    )

    hand.dealt_in_seats = [
        "hero",
        "bb",
        "btn",
    ]

    hand.set_board(
        ["Jd", "9s", "Tc"],
        ts=1.0,
    )

    hand.current_bet_bb = 0.0
    hand.last_aggressor_seat = None

    # Replay 0002 FLOP order:
    #
    # Hero acts first, then BB, then BTN.
    hand.players_to_act = [
        "hero",
        "bb",
        "btn",
    ]

    tracker = BettingRoundTracker(
        hand
    )

    return hand, tracker


def flop_actions(hand):
    return [
        (item.seat, item.action)
        for item in hand.actions
        if item.street == "FLOP"
    ]


def main():
    # ========================================================
    # CONTROL:
    # Existing behavior without a blocker reproduces the bug.
    # ========================================================

    hand, tracker = make_tracker()

    added = tracker.advance_to_observed_actor(
        "bb",
        blocked_seats=set(),
        ts=2.0,
    )

    assert [
        (item.seat, item.action)
        for item in added
    ] == [
        ("hero", "CHECK"),
    ]

    assert hand.players_to_act == [
        "bb",
        "btn",
    ]

    print(
        "after BB observed:",
        flop_actions(hand),
    )

    added = tracker.advance_to_observed_actor(
        "btn",
        blocked_seats=set(),
        ts=3.0,
    )

    assert [
        (item.seat, item.action)
        for item in added
    ] == [
        ("bb", "CHECK"),
    ]

    print(
        "control without blocker:",
        flop_actions(hand),
    )

    assert hand.players_to_act == [
        "btn",
    ]

    # ========================================================
    # CONTRACT:
    # Existing blocked_seats API must preserve BB unresolved.
    # ========================================================

    hand, tracker = make_tracker()

    added = tracker.advance_to_observed_actor(
        "bb",
        blocked_seats=set(),
        ts=2.0,
    )

    assert [
        (item.seat, item.action)
        for item in added
    ] == [
        ("hero", "CHECK"),
    ]

    assert hand.players_to_act == [
        "bb",
        "btn",
    ]

    # BB now has explicit provisional commitment evidence:
    # a transition-sourced visible bet amount exists, but the
    # independent stack pipeline has not corroborated it.
    #
    # That evidence is not sufficient to publish BET.
    # It IS sufficient to prevent proving CHECK.
    added = tracker.advance_to_observed_actor(
        "btn",
        blocked_seats={
            "bb",
        },
        ts=3.0,
    )

    print(
        "with provisional blocker:",
        flop_actions(hand),
    )

    print(
        "returned actions:",
        [
            (item.seat, item.action)
            for item in added
        ],
    )

    print(
        "queue:",
        hand.players_to_act,
    )

    assert added == []

    assert flop_actions(hand) == [
        ("hero", "CHECK"),
    ]

    assert hand.players_to_act == [
        "bb",
        "btn",
    ]

    assert not any(
        item.seat == "bb"
        and item.action == "CHECK"
        for item in hand.actions
    )

    print(
        "PASS existing blocked_seats API prevents "
        "passive CHECK inference across unresolved "
        "provisional commitment evidence"
    )


if __name__ == "__main__":
    main()
