from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand_store import CanonicalHandStore


def main():
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

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "hand_token": "fast-stack-test",
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
                    "players": [
                        {
                            "seat": "seat_upper_right",
                            "stack_bb": 100.0,
                        },
                        {
                            "seat": "hero",
                            "stack_bb": 72.5,
                        },
                        {
                            "seat": "seat_lower_left",
                            "stack_bb": 40.0,
                        },
                    ],
                    "ts": 101.0,
                },
            )

            assert state["canonical_snapshot_ready"] is True

            canonical = sm.CANONICAL_STORE.load()

            # Structural truth is available immediately.
            assert canonical.hero_position == "SB"
            assert canonical.dealt_in_seats == [
                "seat_upper_right",
                "hero",
                "seat_lower_left",
            ]

            assert canonical.players["hero"].position == "SB"
            assert (
                canonical.players["seat_lower_left"].position
                == "BB"
            )

            # Provisional local stack OCR must not become canonical truth.
            hero = canonical.players["hero"]

            assert hero.starting_stack_bb is None
            assert hero.current_stack_bb is None
            assert hero.last_confirmed_stack_bb is None
            assert 72.5 in hero.starting_stack_candidates

            rendered = (
                root / "current_hand.txt"
            ).read_text()

            assert "72.5 BB" not in rendered

            print(
                "PASS fast bootstrap stack contract: "
                "structural context is immediate while local "
                "stack OCR remains provisional"
            )

    finally:
        sm.CANONICAL_STORE = original_store


if __name__ == "__main__":
    main()
