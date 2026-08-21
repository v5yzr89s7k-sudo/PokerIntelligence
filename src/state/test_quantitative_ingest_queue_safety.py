from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="quantitative-queue-safety",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hj",
                "name": "HJ",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="CO",
        positions={
            "utg": "UTG",
            "hj": "HJ",
            "co": "CO",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"
    hand.current_bet_bb = 1.0
    hand.players_to_act = ["utg", "hj", "co"]

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    before_queue = list(hand.players_to_act)

    result = tracker.ingest({
        "episode_id": 1001,
        "seat": "hj",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.98,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.0,
                "stack_read_confidence": 0.98,
                "stack_read_mode": "continuity",
            },
            "table_context": {
                "prior_voluntary_commitment_seats": [],
            },
        },
        "evidence": ["stack_changed"],
        "ts": 2.0,
    })

    # A quantitative observation for HJ does not independently prove
    # what UTG did. Therefore HJ cannot be published through the live
    # queue until chronology has explicitly resolved UTG.
    assert result is None, result

    assert hand.players_to_act == before_queue, (
        hand.players_to_act
    )

    assert hand.actions == [], [
        (a.seat, a.action)
        for a in hand.actions
    ]

    assert hand.players["utg"].folded is False
    assert hand.players["utg"].active is True

    assert 1001 not in tracker.processed_episode_ids

    print(
        "PASS quantitative ingest queue safety: "
        "later quantitative evidence cannot consume or fabricate "
        "unresolved earlier actions"
    )


if __name__ == "__main__":
    main()
