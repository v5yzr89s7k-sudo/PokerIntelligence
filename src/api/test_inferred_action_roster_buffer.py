from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import CanonicalHandStore


def test_inferred_action_publishes_from_fast_table_context():
    original_store = sm.CANONICAL_STORE

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
                    "ts": 100.0,
                },
            )

            players = [
                {
                    "seat": "seat_upper_right",
                    "name": "Villain",
                    "stack_bb": 100.0,
                    "is_active": True,
                },
                {
                    "seat": "hero",
                    "name": "Hero",
                    "stack_bb": 20.0,
                    "is_hero": True,
                    "is_active": True,
                },
                {
                    "seat": "seat_lower_left",
                    "name": "BigBlind",
                    "stack_bb": 40.0,
                    "is_active": True,
                },
            ]

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": "roster-buffer-test",
                    "dealer_button_seat": "seat_upper_right",
                    "hero_position": "SB",
                    "participant_frame_count": 6,
                    "dealt_in_seats": [
                        "seat_upper_right",
                        "hero",
                        "seat_lower_left",
                    ],
                    "positions": {
                        "seat_upper_right": "BTN",
                        "hero": "SB",
                        "seat_lower_left": "BB",
                    },
                    "players": players,
                    "ts": 101.0,
                },
            )

            assert state["canonical_snapshot_ready"] is True

            state = sm.handle_inferred_action(
                state,
                {
                    "type": "inferred_action",
                    "episode_id": 1,
                    "seat": "seat_upper_right",
                    "street": "PREFLOP",
                    "action": "BET_OR_RAISE",
                    "confidence": 0.95,
                    "measurements": {
                        "stack_change": {
                            "delta_bb": 2.2,
                        },
                    },
                    "evidence": [
                        "stack_changed",
                        "bet_region_occupied",
                    ],
                    "ts": 102.0,
                },
            )

            rendered_before_snapshot = (
                root / "current_hand.txt"
            ).read_text()

            # Product invariant:
            # a qualified action must reach current_hand.txt immediately from
            # fast local context. GPT snapshot latency is not on the action
            # publication path.
            assert "opens to 2.2 BB" in rendered_before_snapshot
            assert state["pending_inferred_actions"] == []

            state = sm.handle_table_snapshot(
                state,
                {
                    "type": "table_snapshot",
                    "players": players,
                    "dealer_button_seat": "seat_upper_right",
                    "ts": 103.0,
                },
            )

            rendered_after_snapshot = (
                root / "current_hand.txt"
            ).read_text()

            assert state["canonical_snapshot_ready"] is True
            assert state["pending_inferred_actions"] == []
            assert "Villain" in rendered_after_snapshot
            assert "100 BB" in rendered_after_snapshot
            assert "opens to 2.2 BB" in rendered_after_snapshot
            assert rendered_after_snapshot.count(
                "opens to 2.2 BB"
            ) == 1

            assert (
                rendered_after_snapshot.index("Villain")
                < rendered_after_snapshot.index("opens to 2.2 BB")
            )

    finally:
        sm.CANONICAL_STORE = original_store
