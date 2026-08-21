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

            seats = [
                "seat_upper_right",
                "seat_mid_right",
                "seat_lower_right",
                "hero",
                "seat_lower_left",
                "seat_mid_left",
                "seat_upper_left",
            ]

            positions = {
                "seat_upper_right": "CO",
                "seat_mid_right": "BTN",
                "seat_lower_right": "SB",
                "hero": "BB",
                "seat_lower_left": "UTG",
                "seat_mid_left": "UTG+1",
                "seat_upper_left": "LJ",
            }

            local_players = [
                {
                    "seat": seat,
                    "name": "",
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
                    "is_hero": seat == "hero",
                    "is_active": True,
                }
                for seat in seats
            ]

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": "identity-test",
                    "dealer_button_seat": "seat_mid_right",
                    "dealt_in_seats": seats,
                    "positions": positions,
                    "hero_position": "BB",
                    "players": local_players,
                },
            )

            # Fast structural bootstrap must not invent identities.
            by_seat = {
                p["seat"]: p
                for p in state["players"]
            }

            assert by_seat["seat_mid_left"]["name"] == ""

            # Snapshot deliberately misses seat_mid_left identity.
            snapshot_players = []

            for seat in seats:
                if seat == "seat_mid_left":
                    continue

                snapshot_players.append({
                    "seat": seat,
                    "name": (
                        "poker5068"
                        if seat == "hero"
                        else f"player-{seat}"
                    ),
                    "stack_bb": 50.0,
                    "is_hero": seat == "hero",
                    "is_active": True,
                })

            state = sm.handle_table_snapshot(
                state,
                {
                    "type": "table_snapshot",
                    "hand_token": "identity-test",
                    "players": snapshot_players,
                    "dealt_in_seats": [
                        seat
                        for seat in seats
                        if seat != "seat_mid_left"
                    ],
                    "dealer_button_seat": "seat_mid_right",
                    "positions": positions,
                    "hero_position": "BB",
                    "ts": 1001.0,
                },
            )

            by_seat = {
                p["seat"]: p
                for p in state["players"]
            }

            assert len(by_seat) == 7
            assert by_seat["seat_mid_left"]["name"] == ""

            canonical = sm.CANONICAL_STORE.load()

            assert len(canonical.players) == 7
            assert canonical.players["seat_mid_left"].name == ""

            rendered = (
                root / "current_hand.txt"
            ).read_text()

            # The physical seat must never leak into the user-facing identity.
            assert "seat_mid_left" not in rendered

            # The player itself still exists structurally.
            assert "UTG+1" in rendered

            print(
                "PASS unresolved identity contract: "
                "missing same-seat name stays blank; "
                "physical seat never becomes player name"
            )

    finally:
        sm.CANONICAL_STORE = old_store
        sm.reset_tracker()


if __name__ == "__main__":
    main()
