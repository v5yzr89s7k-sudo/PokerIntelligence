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
                    "hero_cards": ["Ah", "Kd"],
                    "ts": 100.0,
                },
            )

            state = sm.handle_table_context(
                state,
                {
                    "type": "table_context",
                    "ts": 100.1,
                    "hand_token": "bootstrap-test",
                    "dealer_button_seat": "btn",
                    "hero_position": "BB",
                    "dealt_in_seats": [
                        "btn",
                        "sb",
                        "hero",
                        "utg",
                    ],
                    "positions": {
                        "btn": "BTN",
                        "sb": "SB",
                        "hero": "BB",
                        "utg": "UTG",
                    },
                    "players": [
                        {
                            "seat": "btn",
                            "name": "Button",
                            "stack_bb": 136.01,
                            "stack_confidence": 0.98,
                            "stack_read_mode": "agreement_verified",
                            "stack_candidates": [136.01],
                        },
                        {
                            "seat": "sb",
                            "name": "SmallBlind",
                            "stack_bb": None,
                            "stack_confidence": 0.50,
                            "stack_read_mode": "segmentation_disagreement",
                            "stack_candidates": [98.55, 58.55],
                        },
                        {
                            "seat": "hero",
                            "name": "Hero",
                            "stack_bb": 11.78,
                            "stack_confidence": 0.98,
                            "stack_read_mode": "agreement_verified",
                            "stack_candidates": [11.78],
                        },
                        {
                            "seat": "utg",
                            "name": "UTG",
                            "stack_bb": None,
                            "stack_confidence": 0.50,
                            "stack_read_mode": "segmentation_disagreement",
                            "stack_candidates": [48.57, 48.87],
                        },
                    ],
                },
            )

            hand = sm.canonical_load()

            assert hand.players["btn"].starting_stack_bb == 136.01
            assert hand.players["hero"].starting_stack_bb == 11.78

            assert hand.players["sb"].starting_stack_bb is None
            assert hand.players["utg"].starting_stack_bb is None

            assert hand.players["sb"].starting_stack_candidates == [
                98.55,
                58.55,
            ]
            assert hand.players["utg"].starting_stack_candidates == [
                48.57,
                48.87,
            ]

            print(
                "PASS trusted bootstrap stacks: "
                "trusted local values publish immediately; "
                "ambiguous values remain provisional"
            )

    finally:
        sm.CANONICAL_STORE = old_store


if __name__ == "__main__":
    main()
