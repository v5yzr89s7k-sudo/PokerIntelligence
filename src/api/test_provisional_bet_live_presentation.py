from pathlib import Path
import tempfile

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HERO = "hero"
VILLAIN = "villain"


def build_hand():
    hand = CanonicalHand().start_hand(
        hand_id="provisional-live-presentation",
        players=[
            {
                "seat": HERO,
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": VILLAIN,
                "name": "Birkam",
                "stack_bb": 100.0,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["Qd", "Ah"],
        hero_position="SB",
        positions={
            HERO: "SB",
            VILLAIN: "BB",
        },
        started_ts=1.0,
    )

    hand.dealt_in_seats = [HERO, VILLAIN]
    hand.current_street = "RIVER"
    hand.board = ["Jd", "9s", "Tc", "9h", "7h"]

    # Stage 2 begins before Hero's passive predecessor is authoritative.
    # Villain becoming the physical actor must itself resolve Hero CHECK
    # exactly once through handle_actor_observed().
    return hand


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        original_store = sm.CANONICAL_STORE

        try:
            store = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            sm.CANONICAL_STORE = store

            hand = build_hand()
            store.save(hand)

            before_json = (
                root / "canonical_hand.json"
            ).read_text()

            before_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in store.load().actions
            ]

            state = sm.default_state()
            state["phase"] = "RIVER"
            state["hand_token"] = "hand-1"
            state["canonical_snapshot_ready"] = True

            # ========================================================
            # Stage 2 latency contract:
            # raw physical bet-region onset must publish the unsized
            # opening BET before numeric bet transport returns.
            # ========================================================

            state = sm.handle_actor_observed(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": "hand-1",
                    "seat": VILLAIN,
                    "street": "RIVER",
                    "source": "bet_region_appeared",
                    "commitment_visible": True,
                    "blocked_seats": [],
                    "ts": 10.5,
                },
            )

            physical_text = (
                root / "current_hand.txt"
            ).read_text()

            physical_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in store.load().actions
            ]

            print(
                "===== PHYSICAL-ONSET LIVE TEXT ====="
            )
            print(physical_text)

            print(
                "===== PHYSICAL-ONSET CANONICAL ACTIONS ====="
            )
            print(physical_actions)

            assert (
                "BB (Birkam) bets"
                in physical_text
            ), (
                "RED: physical bet-region onset did not publish "
                "the unsized opening BET immediately"
            )

            assert (
                "BB (Birkam) bets 6.75 BB"
                not in physical_text
            ), (
                "RED: physical-onset presentation fabricated "
                "unsettled quantitative sizing"
            )

            assert not any(
                action[0] == VILLAIN
                for action in physical_actions
            ), (
                "RED: physical-onset presentation prematurely "
                "mutated authoritative Villain chronology"
            )

            assert not (
                state.get("unresolved_provisional_bets")
                or {}
            ), (
                "RED: physical presentation incorrectly entered "
                "the quantitative provisional-bet lifecycle"
            )

            print(
                "PASS: physical commitment onset publishes an "
                "unsized BET before quantitative transport"
            )

            # Hero CHECK was legitimately canonicalized by the physical
            # actor-observed transaction above. Reset the mutation baseline
            # here so the Stage-1 assertion below tests only whether opening
            # the later quantitative provisional lifecycle mutates canonical.
            before_json = (
                root / "canonical_hand.json"
            ).read_text()

            before_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in store.load().actions
            ]

            # Existing quantitative provisional lifecycle follows later.
            state = sm.handle_provisional_bet_opened(
                state,
                {
                    "type": "provisional_bet_opened",
                    "hand_token": "hand-1",
                    "seat": VILLAIN,
                    "street": "RIVER",
                    "source": "transition",
                    "source_request_id": "request-1",
                    "bet_bb": 6.75,
                    "ts": 11.0,
                },
            )

            live_text = (
                root / "current_hand.txt"
            ).read_text()

            after_json = (
                root / "canonical_hand.json"
            ).read_text()

            after_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in store.load().actions
            ]

            print("===== LIVE TEXT =====")
            print(live_text)

            print("===== CANONICAL ACTIONS =====")
            print(after_actions)

            assert "SB (Hero) checks" in live_text

            assert "BB (Birkam) bets" in live_text, (
                "RED: unresolved trustworthy RIVER commitment "
                "is not immediately visible in current_hand.txt"
            )

            assert "BB (Birkam) bets 6.75 BB" not in live_text, (
                "RED: provisional presentation exposed an "
                "unsettled quantitative amount"
            )

            assert before_json == after_json, (
                "RED: provisional presentation mutated "
                "canonical_hand.json"
            )

            assert before_actions == after_actions, (
                "RED: provisional presentation mutated "
                "authoritative canonical actions"
            )

            assert not any(
                action[0] == VILLAIN
                for action in after_actions
            ), (
                "RED: provisional BET was inserted into "
                "canonical chronology"
            )

            print(
                "PASS: provisional BET is immediately visible "
                "without mutating authoritative canonical state"
            )

            # ========================================================
            # Settlement lifecycle:
            # provisional unsized BET -> one canonical sized BET.
            # ========================================================

            settled = store.load()

            settled.add_action(
                seat=VILLAIN,
                action="BET",
                amount_bb=6.75,
                confidence=0.99,
                source="quantitative_settlement",
                evidence=["stack_and_bet_corroborated"],
                ts=12.0,
            )

            store.save(settled)

            state = sm.handle_provisional_bet_closed(
                state,
                {
                    "type": "provisional_bet_closed",
                    "hand_token": "hand-1",
                    "seat": VILLAIN,
                    "street": "RIVER",
                    "reason": "corroborated",
                    "source_request_id": "request-1",
                    "ts": 12.1,
                },
            )

            settled_text = (
                root / "current_hand.txt"
            ).read_text()

            settled_hand = store.load()

            settled_actions = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in settled_hand.actions
            ]

            print("===== SETTLED LIVE TEXT =====")
            print(settled_text)

            print("===== SETTLED CANONICAL ACTIONS =====")
            print(settled_actions)

            assert (
                "BB (Birkam) bets 6.75 BB"
                in settled_text
            ), (
                "RED: canonical quantitative settlement did not "
                "replace provisional BET with sized BET"
            )

            assert (
                settled_text.count("BB (Birkam) bets")
                == 1
            ), (
                "RED: provisional and canonical BET were both "
                "rendered after settlement"
            )

            assert (
                "RIVER:villain"
                not in (
                    state.get("unresolved_provisional_bets")
                    or {}
                )
            ), (
                "RED: settled provisional BET remained open"
            )

            villain_actions = [
                action
                for action in settled_actions
                if action[0] == VILLAIN
            ]

            assert villain_actions == [
                (
                    VILLAIN,
                    "BET",
                    6.75,
                    None,
                )
            ], (
                "RED: settlement did not produce exactly one "
                "authoritative Villain BET"
            )

            print(
                "PASS: provisional BET cleanly upgrades to one "
                "sized canonical BET with no duplicate chronology"
            )

        finally:
            sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
