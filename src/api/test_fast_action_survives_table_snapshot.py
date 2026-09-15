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

            # CanonicalHandStore.save() is persistence-only in v0.16.
            # Establish the test's initial live presentation explicitly;
            # subsequent action publication must use the production
            # presentation gateway.
            store.save(hand)
            store.save_live_presentation(
                hand,
                provisional_actions=None,
            )

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
            # Establish one already-owned live opponent action.
            #
            # Raw opponent bet-region appearance is intentionally
            # provisional in v0.16 and cannot author an action by itself.
            # This regression is about presentation persistence across
            # asynchronous table_snapshot enrichment, so seed the existing
            # ActionTimeline owner explicitly and publish through the normal
            # live-presentation gateway.
            # ----------------------------------------------------

            from src.state.action_timeline import (
                observe_action,
                presentation_overlay,
            )

            state = observe_action(
                state,
                hand_token=TOKEN,
                street="PREFLOP",
                seat=UTG,
                action="BET_OR_RAISE",
                ts=2.0,
                source="test_owned_action",
                confidence=1.0,
                evidence=[
                    "test_owned_action",
                ],
            )

            state[
                "pending_live_commitments"
            ] = presentation_overlay(
                state
            )

            state = sm.refresh_live_presentation(
                state,
                publication_intent="action",
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

            assert any(
                str(item.get("street") or "").upper()
                == "PREFLOP"
                and item.get("seat") == UTG
                for item in (
                    state.get("action_timeline")
                    or []
                )
            )

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

            assert any(
                str(item.get("street") or "").upper()
                == "PREFLOP"
                and item.get("seat") == UTG
                for item in (
                    state.get("action_timeline")
                    or []
                )
            ), (
                "BUG: unrelated table snapshot retired "
                "valid ActionTimeline ownership"
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
