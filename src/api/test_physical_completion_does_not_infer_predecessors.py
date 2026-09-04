from unittest.mock import patch

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="physical-no-predecessor-inference",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "lj",
                "name": "LJ",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "hj",
                "name": "HJ",
                "stack_bb": 50.0,
                "is_active": True,
            },
            {
                "seat": "co",
                "name": "CO",
                "stack_bb": 50.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="UTG",
        positions={
            "hero": "UTG",
            "lj": "LJ",
            "hj": "HJ",
            "co": "CO",
        },
        started_ts=1.0,
    )

    hand.players_to_act = [
        "hero",
        "lj",
        "hj",
        "co",
    ]

    return hand


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    state = sm.default_state()
    state["phase"] = "PREFLOP"
    state["canonical_snapshot_ready"] = True
    state["hand_token"] = "physical-no-predecessor-token"

    event = {
        "type": "physical_actor_completed",
        "hand_token": "physical-no-predecessor-token",
        "seat": "co",
        "street": "PREFLOP",
        "source": "opponent_card_disappearance",
        "evidence": [
            "opponent_cards_visible_before",
            "opponent_cards_absent_after",
            "calibrated_acr_card_back",
        ],
        "ts": 10.0,
    }

    before_queue = list(hand.players_to_act)

    with patch.object(
        sm,
        "canonical_load",
        return_value=hand,
    ), patch.object(
        sm,
        "canonical_save",
    ), patch.object(
        sm,
        "tracker_for_hand",
        return_value=tracker,
    ):
        state = sm.handle_physical_actor_completed(
            state,
            event,
        )

    assert hand.players_to_act == before_queue, (
        "RED: later physical completion mutated canonical chronology"
    )

    assert hand.actions == [], (
        "RED: later physical completion fabricated predecessor actions"
    )

    assert not hand.players["hero"].folded
    assert not hand.players["lj"].folded
    assert not hand.players["hj"].folded
    assert not hand.players["co"].folded

    pending = list(
        state.get("pending_physical_actor_completions")
        or []
    )

    assert len(pending) == 1
    assert pending[0]["seat"] == "co"

    print(
        "PASS physical completion isolation: "
        "later-seat card disappearance is preserved without "
        "fabricating predecessor actions"
    )


if __name__ == "__main__":
    main()
