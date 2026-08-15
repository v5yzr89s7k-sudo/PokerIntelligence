from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def main():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="late-boundary-current-queue",
        players=[
            {
                "seat": "seat_upper_right",
                "name": "SB",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_mid_right",
                "name": "BB",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_mid_left",
                "name": "HJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_upper_left",
                "name": "CO",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "seat_top",
                "name": "BTN",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="UTG+1",
        positions={
            "seat_upper_right": "SB",
            "seat_mid_right": "BB",
            "hero": "UTG+1",
            "seat_mid_left": "HJ",
            "seat_upper_left": "CO",
            "seat_top": "BTN",
        },
        started_ts=1.0,
    )

    hand.set_board(
        ["8d", "8h", "As", "Jh"],
        ts=2.0,
    )

    tracker = BettingRoundTracker(hand)
    street = "TURN"

    # Hero has already acted on TURN.
    hand.players_to_act = [
        seat
        for seat in hand.players_to_act
        if seat != "hero"
    ]

    tracker.commitment_tracker.sync_queue(
        street,
        hand.players_to_act,
    )

    before = (
        tracker.commitment_tracker
        .players_owing_action(street)
    )

    assert "hero" not in before, before
    assert "seat_mid_right" in before, before
    assert "seat_upper_left" in before, before
    assert "seat_top" in before, before

    # Late FLOP boundary evidence now proves these players folded.
    for seat in (
        "seat_mid_right",
        "seat_upper_left",
        "seat_top",
    ):
        hand.players[seat].folded = True

    eligible = [
        seat
        for seat, player in hand.players.items()
        if player.active
        and not player.folded
        and not player.all_in
    ]

    hand.players_to_act = [
        seat
        for seat in hand.players_to_act
        if seat in eligible
    ]

    tracker.commitment_tracker.reconcile_eligible_seats(
        street,
        eligible,
    )

    after = (
        tracker.commitment_tracker
        .players_owing_action(street)
    )

    assert after == [
        "seat_upper_right",
        "seat_mid_left",
    ], after

    # Critical safety invariant: filtering stale eligibility must not
    # resurrect Hero after Hero's TURN action was already consumed.
    assert "hero" not in after, after

    print(
        "PASS late boundary current-queue reconciliation: "
        "late folds are removed without resurrecting "
        "already-consumed current-street actions"
    )


if __name__ == "__main__":
    main()
