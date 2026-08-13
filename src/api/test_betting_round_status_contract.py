from pathlib import Path
from tempfile import TemporaryDirectory

from src.api import api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def build_hand():
    players = [
        {
            "seat": "seat_top",
            "name": "UTG",
            "stack_bb": 100.0,
            "is_active": True,
        },
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 100.0,
            "is_active": True,
        },
    ]

    hand = CanonicalHand().start_hand(
        hand_id="canonical-test-hand",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="BB",
        positions={
            "seat_top": "UTG",
            "hero": "BB",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = ["seat_top", "hero"]
    hand.current_street = "PREFLOP"

    return hand


def main():
    hand = build_hand()
    tracker = BettingRoundTracker(hand)

    # Match BettingRoundTracker's real initialization contract:
    # immutable street order plus the current traversal queue.
    tracker.commitment_tracker.initialize_street_order(
        "PREFLOP",
        ["seat_top", "hero"],
    )
    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        ["seat_top", "hero"],
    )

    state = {
        "hand_token": "live-token-123",
    }

    original_path = sm.BETTING_ROUND_STATUS_PATH

    with TemporaryDirectory() as tmp:
        sm.BETTING_ROUND_STATUS_PATH = (
            Path(tmp) / "betting_round_status.json"
        )

        try:
            status = sm.write_betting_round_status(
                tracker,
                hand,
                state,
            )
        finally:
            sm.BETTING_ROUND_STATUS_PATH = original_path

    assert status["hand_id"] == "canonical-test-hand"
    assert status["hand_token"] == "live-token-123"
    assert status["street"] == "PREFLOP"
    assert status["players_owing_action"] == [
        "seat_top",
        "hero",
    ]

    print(
        "PASS betting round status contract: "
        "authoritative obligations carry both canonical hand_id "
        "and live hand_token"
    )


if __name__ == "__main__":
    main()
