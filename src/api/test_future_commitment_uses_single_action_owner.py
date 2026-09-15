from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.action_timeline import (
    active_actions,
    presentation_overlay,
)

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


TOKEN = "future-single-owner"
SEAT = "actor"
FUTURE_FUNCTION = "record_future_street_live_commitment"


def main():
    old_store = sm.CANONICAL_STORE

    future_handler = getattr(
        sm,
        FUTURE_FUNCTION,
    )

    with TemporaryDirectory() as tmp:
        try:
            root = Path(tmp)

            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical.json",
                text_path=root / "current_hand.txt",
            )

            hand = CanonicalHand().start_hand(
                hand_id=TOKEN,
                players=[
                    {
                        "seat": SEAT,
                        "name": "Actor",
                        "stack_bb": 100.0,
                        "is_hero": False,
                        "is_active": True,
                    },
                ],
                hero_cards=[],
                hero_position="unknown",
                positions={
                    SEAT: "X",
                },
                started_ts=1.0,
            )

            hand.current_street = "PREFLOP"

            sm.CANONICAL_STORE.save(
                hand
            )

            state = sm.default_state()

            state["hand_token"] = TOKEN
            state["phase"] = "PREFLOP"
            state["canonical_snapshot_ready"] = True

            state = future_handler(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": TOKEN,
                    "street": "FLOP",
                    "seat": SEAT,
                    "source": "bet_region_appeared",
            "commitment_visible": True,
                    "ts": 2.0,
                },
            )

            actions = active_actions(
                state,
                TOKEN,
            )

            print(
                "future observed:",
                actions,
            )

            assert len(actions) == 1
            assert actions[0]["street"] == "FLOP"
            assert actions[0]["seat"] == SEAT
            assert actions[0]["action"] == "COMMITMENT"

            assert (
                "FLOP:actor"
                in presentation_overlay(state)
            )

            state = sm.handle_provisional_bet_closed(
                state,
                {
                    "type": "provisional_bet_closed",
                    "hand_token": TOKEN,
                    "street": "FLOP",
                    "seat": SEAT,
                    "reason": "resolved",
                    "ts": 3.0,
                },
            )

            actions = active_actions(
                state,
                TOKEN,
            )

            print(
                "after enrichment close:",
                actions,
            )

            assert len(actions) == 1, (
                "provisional close erased future action"
            )

            state = sm.handle_action_observation_rejected(
                state,
                {
                    "type": "action_observation_rejected",
                    "hand_token": TOKEN,
                    "street": "FLOP",
                    "seat": SEAT,
                    "reason": "physical_commitment_invalidated",
                    "ts": 3.1,
                },
            )

            actions = active_actions(
                state,
                TOKEN,
            )

            print(
                "after explicit rejection:",
                actions,
            )

            assert actions == []

            print()
            print(
                "PASS: future physical evidence uses "
                "the same durable action owner"
            )

        finally:
            sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
