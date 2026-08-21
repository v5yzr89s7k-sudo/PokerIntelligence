from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import (
    CanonicalHandStore,
)


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
                    "hero_cards": ["Ah", "Kd"],
                    "ts": 1.0,
                },
            )

            state["hand_token"] = "board-gate-test"

            positions = {
                "utg": "UTG",
                "sb": "SB",
                "hero": "BB",
            }

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": state["hand_token"],
                    "dealer_button_seat": "utg",
                    "hero_position": "BB",
                    "dealt_in_seats": [
                        "utg",
                        "sb",
                        "hero",
                    ],
                    "positions": positions,
                    "players": [
                        {"seat": "utg"},
                        {"seat": "sb"},
                        {"seat": "hero"},
                    ],
                    "ts": 1.1,
                },
            )

            canonical = sm.CANONICAL_STORE.load()
            tracker = sm.tracker_for_hand(canonical)

            # Model an open SB raise with Hero already responding and UTG still
            # owing the final preflop response.
            tracker.commitment_tracker.reset_street(
                "PREFLOP"
            )
            tracker.commitment_tracker.initialize_street_order(
                "PREFLOP",
                ["utg", "sb", "hero"],
            )
            tracker.commitment_tracker.sync_queue(
                "PREFLOP",
                ["utg", "sb", "hero"],
            )

            tracker.commitment_tracker.consume_pending_action(
                "PREFLOP",
                "utg",
            )
            tracker.commitment_tracker.record_action(
                "PREFLOP",
                "utg",
            )

            tracker.commitment_tracker.consume_pending_action(
                "PREFLOP",
                "sb",
            )

            tracker.commitment_tracker.open_response_queue(
                "PREFLOP",
                "sb",
                ["utg", "hero"],
            )

            tracker.commitment_tracker.record_action(
                "PREFLOP",
                "sb",
                current_price=2.5,
                last_aggressor="sb",
                betting_open=True,
            )

            tracker.commitment_tracker.record_response(
                "PREFLOP",
                "hero",
            )
            tracker.commitment_tracker.record_action(
                "PREFLOP",
                "hero",
            )

            status = tracker.commitment_tracker.round_status(
                "PREFLOP"
            )

            assert status["complete"] is False
            assert status["players_owing_action"] == [
                "utg"
            ]

            # Physical/API board confirmation arrives early.
            state = sm.handle_board(
                state,
                {
                    "type": "board",
                    "board": ["Jd", "9s", "Tc"],
                    "ts": 2.0,
                },
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "PREFLOP"
            assert state.get("board") in (
                None,
                [],
            )
            assert canonical.current_street == "PREFLOP"
            assert canonical.board == []
            assert len(
                state.get("pending_board_events")
                or []
            ) == 1

            # Resolve exactly the currently owed actor.
            tracker.commitment_tracker.record_response(
                "PREFLOP",
                "utg",
            )
            tracker.commitment_tracker.record_action(
                "PREFLOP",
                "utg",
            )

            status = tracker.commitment_tracker.round_status(
                "PREFLOP"
            )

            assert status["complete"] is True
            assert status["players_owing_action"] == []

            state = sm.release_pending_board_if_ready(
                state
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["phase"] == "FLOP"
            assert state["board"] == [
                "Jd",
                "9s",
                "Tc",
            ]
            assert canonical.current_street == "FLOP"
            assert canonical.board == [
                "Jd",
                "9s",
                "Tc",
            ]
            assert (
                state.get("pending_board_events")
                or []
            ) == []

            print(
                "PASS board chronology gate: "
                "confirmed FLOP waits while UTG owes action "
                "and promotes immediately after PREFLOP completes"
            )

    finally:
        sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
