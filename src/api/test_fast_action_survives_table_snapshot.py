from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


UTG = "seat_utg"
HERO = "hero"
TOKEN = "table-snapshot-persistence-test"


def build_hand():
    hand = CanonicalHand().start_hand(
        hand_id="table-snapshot-persistence",
        players=[
            {
                "seat": UTG,
                "name": "",
                "stack_bb": 100.0,
                "is_hero": False,
                "is_active": True,
            },
            {
                "seat": HERO,
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="HJ",
        positions={
            UTG: "UTG",
            HERO: "HJ",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        UTG,
        HERO,
    ]

    hand.current_street = "PREFLOP"

    return hand


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        original_store = sm.CANONICAL_STORE
        original_tracker = sm._ACTIVE_TRACKER
        original_hand_id = sm._ACTIVE_HAND_ID

        try:
            store = CanonicalHandStore(
                json_path=(
                    root
                    / "canonical_hand.json"
                ),
                text_path=(
                    root
                    / "current_hand.txt"
                ),
            )

            sm.CANONICAL_STORE = store
            sm._ACTIVE_TRACKER = None
            sm._ACTIVE_HAND_ID = None

            hand = build_hand()
            store.save(hand)

            state = sm.default_state()

            state["phase"] = "PREFLOP"
            state["hand_token"] = TOKEN
            state[
                "canonical_snapshot_ready"
            ] = True

            state["players"] = [
                {
                    "seat": UTG,
                    "name": "",
                    "stack_bb": 100.0,
                    "is_hero": False,
                    "is_active": True,
                },
                {
                    "seat": HERO,
                    "name": "Hero",
                    "stack_bb": 50.0,
                    "is_hero": True,
                    "is_active": True,
                },
            ]

            state["positions"] = {
                UTG: "UTG",
                HERO: "HJ",
            }

            state["dealt_in_seats"] = [
                UTG,
                HERO,
            ]

            # ----------------------------------------------------
            # Stage 1:
            # Fast physical commitment reaches TXT immediately.
            # ----------------------------------------------------

            state = sm.record_physical_live_commitment(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": TOKEN,
                    "street": "PREFLOP",
                    "seat": UTG,
                    "source": "bet_region_appeared",
                    "commitment_visible": True,
                    "ts": 2.0,
                },
            )

            before = store.text_path.read_text()

            print(
                "===== BEFORE TABLE SNAPSHOT ====="
            )
            print(before)

            assert "UTG bets or raises" in before, (
                "setup failure: fast UTG action "
                "did not reach TXT"
            )

            pending_before = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            print(
                "pending before:",
                pending_before,
            )

            assert "PREFLOP:seat_utg" in pending_before

            # Canonical still intentionally does NOT own UTG action.
            canonical = store.load()

            assert not [
                action
                for action in canonical.actions
                if action.seat == UTG
                and action.action.upper()
                not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                }
            ]

            # ----------------------------------------------------
            # Stage 2:
            # Slow asynchronous table snapshot enriches roster.
            #
            # This reproduces the live overwrite that erased the
            # already-visible UTG action.
            # ----------------------------------------------------

            state = sm.handle_table_snapshot(
                state,
                {
                    "type": "table_snapshot",
                    "hand_token": TOKEN,
                    "hero_position": "HJ",
                    "dealer_button_seat": "",
                    "dealt_in_seats": [
                        UTG,
                        HERO,
                    ],
                    "players": [
                        {
                            "seat": UTG,
                            "name": "LownWolf",
                            "stack_text": "100 BB",
                            "stack_bb": 100.0,
                            "is_hero": False,
                            "is_active": True,
                        },
                        {
                            "seat": HERO,
                            "name": "Hero",
                            "stack_text": "50 BB",
                            "stack_bb": 50.0,
                            "is_hero": True,
                            "is_active": True,
                        },
                    ],
                    "confidence": 1.0,
                    "ts": 3.0,
                },
            )

            after = store.text_path.read_text()

            print()
            print(
                "===== AFTER TABLE SNAPSHOT ====="
            )
            print(after)

            pending_after = dict(
                state.get(
                    "pending_live_commitments"
                )
                or {}
            )

            print(
                "pending after:",
                pending_after,
            )

            assert "LownWolf" in after, (
                "table snapshot enrichment did not apply"
            )

            assert "UTG" in after

            assert "bets or raises" in after, (
                "BUG: table snapshot erased "
                "already-published fast UTG action"
            )

            assert (
                "PREFLOP:seat_utg"
                in pending_after
            ), (
                "BUG: unrelated table snapshot retired "
                "valid fast presentation ownership"
            )

            canonical = store.load()

            assert not [
                action
                for action in canonical.actions
                if action.seat == UTG
                and action.action.upper()
                not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                }
            ], (
                "presentation persistence improperly "
                "created canonical action"
            )

            print()
            print(
                "PASS: fast UTG action survives "
                "slow table-snapshot enrichment"
            )

        finally:
            sm.CANONICAL_STORE = (
                original_store
            )

            sm._ACTIVE_TRACKER = (
                original_tracker
            )

            sm._ACTIVE_HAND_ID = (
                original_hand_id
            )


if __name__ == "__main__":
    main()
