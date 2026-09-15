from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.action_timeline import (
    active_actions,
    presentation_overlay,
)

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


TOKEN = "enrichment-close-separation"
SEAT = "hero"


def main():
    old_store = sm.CANONICAL_STORE

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
                        "name": "Hero",
                        "stack_bb": 50.0,
                        "is_hero": True,
                        "is_active": True,
                    },
                ],
                hero_cards=["As", "Kd"],
                hero_position="BTN",
                positions={
                    SEAT: "BTN",
                },
                started_ts=1.0,
            )

            hand.current_street = "FLOP"

            sm.CANONICAL_STORE.save(
                hand
            )

            state = sm.default_state()

            state["hand_token"] = TOKEN
            state["phase"] = "FLOP"
            state["canonical_snapshot_ready"] = True

            state = sm.record_physical_live_commitment(
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

            before = active_actions(
                state,
                TOKEN,
            )

            print(
                "before close:",
                before,
            )

            assert len(before) == 1

            state = sm.handle_provisional_bet_closed(
                state,
                {
                    "type": "provisional_bet_closed",
                    "hand_token": TOKEN,
                    "street": "FLOP",
                    "seat": SEAT,
                    "reason": "stack_candidate_uncorroborated",
                    "ts": 4.5,
                },
            )

            after_close = active_actions(
                state,
                TOKEN,
            )

            print(
                "after enrichment close:",
                after_close,
            )

            assert len(after_close) == 1, (
                "enrichment close erased durable action"
            )

            assert (
                "FLOP:hero"
                in presentation_overlay(state)
            ), (
                "enrichment close erased presentation "
                "projection"
            )

            state = sm.handle_action_observation_rejected(
                state,
                {
                    "type": "action_observation_rejected",
                    "hand_token": TOKEN,
                    "street": "FLOP",
                    "seat": SEAT,
                    "reason": "physical_commitment_invalidated",
                    "ts": 5.0,
                },
            )

            after_reject = active_actions(
                state,
                TOKEN,
            )

            print(
                "after explicit rejection:",
                after_reject,
            )

            assert after_reject == []

            assert (
                presentation_overlay(state)
                == {}
            )

            print()
            print(
                "PASS: enrichment close cannot erase action; "
                "explicit contradiction can"
            )

        finally:
            sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
