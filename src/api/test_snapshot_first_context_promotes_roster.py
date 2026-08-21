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
                json_path=root / "current_hand.json",
                text_path=root / "current_hand.txt",
            )

            state = sm.default_state()

            state = sm.handle_hero_cards(
                state,
                {
                    "type": "hero_cards",
                    "hero_cards": ["Qd", "Ah"],
                    "ts": 1000.0,
                },
            )

            seven = [
                "seat_upper_right",
                "seat_mid_right",
                "seat_lower_right",
                "hero",
                "seat_lower_left",
                "seat_mid_left",
                "seat_upper_left",
            ]

            six = [
                seat
                for seat in seven
                if seat != "seat_mid_left"
            ]

            seven_positions = {
                "seat_upper_right": "CO",
                "seat_mid_right": "BTN",
                "seat_lower_right": "SB",
                "hero": "BB",
                "seat_lower_left": "UTG",
                "seat_mid_left": "UTG+1",
                "seat_upper_left": "LJ",
            }

            six_positions = {
                "seat_upper_right": "CO",
                "seat_mid_right": "BTN",
                "seat_lower_right": "SB",
                "hero": "BB",
                "seat_lower_left": "UTG",
                "seat_upper_left": "HJ",
            }

            snapshot_players = [
                {
                    "seat": seat,
                    "name": f"name-{seat}",
                    "stack_bb": 50.0,
                    "stack_text": "50 BB",
                    "is_hero": seat == "hero",
                    "is_active": True,
                }
                for seat in six
            ]

            # Production race: snapshot arrives FIRST.
            state = sm.handle_table_snapshot(
                state,
                {
                    "type": "table_snapshot",
                    "hand_token": "hand-seven",
                    "players": snapshot_players,
                    "dealt_in_seats": six,
                    "dealer_button_seat": "seat_mid_right",
                    "positions": six_positions,
                    "hero_position": "BB",
                    "ts": 1000.5,
                },
            )

            before = sm.CANONICAL_STORE.load()

            assert len(before.players) == 6
            assert len(before.dealt_in_seats) == 6

            local_players = [
                {
                    "seat": seat,
                    "name": seat,
                    "stack_bb": (
                        17.85
                        if seat == "seat_mid_left"
                        else None
                    ),
                    "stack_confidence": (
                        0.98
                        if seat == "seat_mid_left"
                        else 0.0
                    ),
                    "stack_candidates": (
                        [17.85]
                        if seat == "seat_mid_left"
                        else []
                    ),
                    "is_hero": seat == "hero",
                    "is_active": True,
                }
                for seat in seven
            ]

            # Stronger local structural truth arrives SECOND.
            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": "hand-seven",
                    "dealer_button_seat": "seat_mid_right",
                    "dealt_in_seats": seven,
                    "positions": seven_positions,
                    "hero_position": "BB",
                    "players": local_players,
                    "ts": 1000.6,
                },
            )

            canonical = sm.CANONICAL_STORE.load()

            assert state["dealt_in_seats"] == seven
            assert len(state["players"]) == 7

            assert canonical.dealt_in_seats == seven
            assert len(canonical.players) == 7

            assert (
                canonical.players["seat_mid_left"].position
                == "UTG+1"
            )
            assert (
                canonical.players["seat_upper_left"].position
                == "LJ"
            )

            # Snapshot enrichment for already-known seats survives promotion.
            assert (
                canonical.players["seat_upper_right"].name
                == "name-seat_upper_right"
            )
            assert (
                canonical.players["seat_upper_right"].starting_stack_bb
                == 50.0
            )

            # Newly promoted local seat survives with trusted local stack.
            assert (
                canonical.players["seat_mid_left"].starting_stack_bb
                == 17.85
            )

            rendered = (
                root / "current_hand.txt"
            ).read_text()

            assert "TABLE — 7 players" in rendered
            assert "UTG+1" in rendered
            assert "LJ" in rendered

            print(
                "PASS snapshot-first/context-second race: "
                "6-player canonical hand promotes to 7 players "
                "without losing snapshot enrichment"
            )

    finally:
        sm.CANONICAL_STORE = old_store
        sm.reset_tracker()


if __name__ == "__main__":
    main()
