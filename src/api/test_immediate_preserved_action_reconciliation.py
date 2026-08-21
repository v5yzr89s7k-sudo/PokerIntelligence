from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import CanonicalHandStore


def main():
    old_store = sm.CANONICAL_STORE

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            state = sm.default_state()

            state = sm.handle_hero_cards(
                state,
                {
                    "type": "hero_cards",
                    "hero_cards": ["Qd", "Ah"],
                    "ts": 1.0,
                },
            )

            # Production coordinator owns a non-empty token for every live
            # hand. Historical preservation deliberately rejects unowned
            # evidence, so the synthetic fixture must model that contract.
            state["hand_token"] = "immediate-reconcile-hand"

            positions = {
                "utg": "UTG",
                "hj": "HJ",
                "co": "CO",
                "btn": "BTN",
                "sb": "SB",
                "hero": "BB",
            }

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": state["hand_token"],
                    "dealer_button_seat": "btn",
                    "hero_position": "BB",
                    "dealt_in_seats": list(positions),
                    "positions": positions,
                    "players": [
                        {"seat": seat}
                        for seat in positions
                    ],
                    "ts": 1.1,
                },
            )

            canonical = sm.CANONICAL_STORE.load()
            tracker = sm.tracker_for_hand(canonical)

            for seat in ("utg", "sb", "hero"):
                tracker.commitment_tracker.record_commitment(
                    "PREFLOP",
                    seat,
                )

            # SB and Hero semantic evidence is already known but blocked by
            # the earlier committed UTG actor.
            key = (
                f"{state['hand_token']}:PREFLOP"
            )

            # Production only accepts stale qualified actions when the
            # street transition has established preserved boundary context.
            state["preserved_boundary_evidence"] = {
                key: {
                    "hand_token": state["hand_token"],
                    "street": "PREFLOP",
                    "request_id": "boundary-test",
                    "observations_by_seat": {},
                    "last_result_ts": 8.0,
                }
            }

            state["preserved_inferred_actions"] = {
                key: {
                    "hand_token": state["hand_token"],
                    "street": "PREFLOP",
                    "actions_by_seat": {
                        "sb": {
                            "street": "PREFLOP",
                            "seat": "sb",
                            "action": "BET_OR_RAISE",
                            "delta_bb": 2.0,
                            "confidence": 0.98,
                            "evidence": [
                                "stack_changed",
                                "bet_region_occupied",
                            ],
                            "ts": 6.0,
                        },
                        "hero": {
                            "street": "PREFLOP",
                            "seat": "hero",
                            "action": "CALL_OR_RAISE",
                            "delta_bb": 1.5,
                            "confidence": 0.98,
                            "evidence": ["stack_changed"],
                            "ts": 7.0,
                        },
                    },
                }
            }

            # Board has already advanced before UTG semantic qualification.
            canonical = sm.CANONICAL_STORE.load()
            canonical.set_board(
                ["Jd", "9s", "Tc"],
                ts=8.0,
            )
            sm.CANONICAL_STORE.save(canonical)

            state["phase"] = "FLOP"

            # Late UTG qualification must immediately unlock the complete
            # historical PREFLOP chronology.
            state = sm.handle_inferred_action(
                state,
                {
                    "type": "inferred_action",
                    "episode_id": 4,
                    "street": "PREFLOP",
                    "seat": "utg",
                    "action": "CALL_OR_RAISE",
                    "delta_bb": 1.0,
                    "confidence": 0.98,
                    "evidence": ["stack_changed"],
                    "ts": 2.0,
                },
            )

            canonical = sm.CANONICAL_STORE.load()

            voluntary = [
                (
                    action.seat,
                    action.action,
                    action.amount_bb,
                    action.raise_to_bb,
                )
                for action in canonical.actions
                if action.street == "PREFLOP"
                and action.action not in {
                    "POST_SMALL_BLIND",
                    "POST_BIG_BLIND",
                }
            ]

            assert voluntary == [
                ("utg", "CALL", 1.0, None),
                ("hj", "FOLD", None, None),
                ("co", "FOLD", None, None),
                ("btn", "FOLD", None, None),
                ("sb", "RAISE", None, 2.5),
                ("hero", "CALL", 1.5, None),
            ], voluntary

            assert canonical.current_street == "FLOP"

            rendered = (
                root / "current_hand.txt"
            ).read_text()

            print()
            print("===== RENDERED HAND =====")
            print(rendered)

            canonical = sm.CANONICAL_STORE.load()
            tracker = sm.tracker_for_hand(canonical)

            print("===== PREFLOP OBLIGATION AFTER RECONCILIATION =====")
            print(
                tracker.commitment_tracker.round_status(
                    "PREFLOP"
                )
            )

            # Chronology through Hero's call must exist immediately.
            assert any(
                a.street == "PREFLOP"
                and a.seat == "utg"
                and a.action == "CALL"
                for a in canonical.actions
            )

            assert any(
                a.street == "PREFLOP"
                and a.seat == "sb"
                and a.action == "RAISE"
                and a.raise_to_bb == 2.5
                for a in canonical.actions
            )

            assert any(
                a.street == "PREFLOP"
                and a.seat == "hero"
                and a.action == "CALL"
                and a.amount_bb == 1.5
                for a in canonical.actions
            )

            # Critical poker invariant:
            # after SB raises and BB calls, UTG still owes a response.
            status = (
                tracker.commitment_tracker
                .round_status("PREFLOP")
            )

            assert status["complete"] is False
            assert status["players_owing_action"] == ["utg"]

            assert key not in state.get(
                "preserved_inferred_actions",
                {},
            )

            print(
                "PASS immediate preserved reconciliation: "
                "late UTG qualification immediately publishes complete "
                "PREFLOP chronology without waiting for boundary worker"
            )

    finally:
        sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
