from pathlib import Path
from tempfile import TemporaryDirectory
import time

import src.api.api_event_state_machine as state_machine
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


with TemporaryDirectory() as tmp:
    root = Path(tmp)

    store = CanonicalHandStore(
        json_path=root / "canonical_hand.json",
        text_path=root / "current_hand.txt",
    )

    hand = CanonicalHand().start_hand(
        hand_id="hero-fold-test",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 65.89,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_mid_right",
                "name": "Villain",
                "stack_bb": 105.22,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["6h", "8d"],
        hero_position="BTN",
        positions={
            "hero": "BTN",
            "seat_mid_right": "HJ",
        },
        started_ts=time.time(),
    )

    hand.set_board(["Qd", "Jd", "7d"])
    store.save(hand)

    original_store = state_machine.CANONICAL_STORE

    try:
        state_machine.CANONICAL_STORE = store

        state = state_machine.default_state()
        state["phase"] = "FLOP"
        state["hero_to_act"] = False

        updated = state_machine.handle_hero_fold(
            state,
            {
                "type": "hero_fold",
                "street": "FLOP",
                "ts": time.time(),
            },
        )

        restored = store.load()
        rendered = store.text_path.read_text()

        hero_folds = [
            action
            for action in restored.actions
            if action.seat == "hero" and action.action == "FOLD"
        ]

        assert len(hero_folds) == 1
        assert hero_folds[0].street == "FLOP"
        assert "BTN (Hero) folds" in rendered
        assert updated["hero_to_act"] is False

        # Duplicate delivery must not create a second fold.
        state_machine.handle_hero_fold(
            updated,
            {
                "type": "hero_fold",
                "street": "FLOP",
                "ts": time.time(),
            },
        )

        restored_again = store.load()
        duplicate_folds = [
            action
            for action in restored_again.actions
            if action.seat == "hero" and action.action == "FOLD"
        ]

        assert len(duplicate_folds) == 1

    finally:
        state_machine.CANONICAL_STORE = original_store

print("Hero fold canonical regression test passed.")
