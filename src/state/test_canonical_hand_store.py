from pathlib import Path
from tempfile import TemporaryDirectory

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


with TemporaryDirectory() as tmp:
    root = Path(tmp)

    store = CanonicalHandStore(
        json_path=root / "canonical_hand.json",
        text_path=root / "current_hand_canonical.txt",
    )

    hand = CanonicalHand().start_hand(
        hand_id="store-test",
        players=[
            {
                "seat": "seat_mid_left",
                "name": "Alice",
                "stack_bb": 22.0,
                "is_hero": False,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 18.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["Qh", "Qs"],
        hero_position="BB",
        positions={
            "seat_mid_left": "BTN",
            "hero": "BB",
        },
        started_ts=1_700_000_000.0,
    )

    hand.add_action(
        "seat_mid_left",
        "RAISE",
        raise_to_bb=2.2,
        ts=1_700_000_001.0,
    )

    store.save(hand)

    assert store.json_path.exists()
    assert store.text_path.exists()

    restored = store.load()

    assert restored.hand_id == "store-test"
    assert restored.hero_cards == ["Qh", "Qs"]
    assert len(restored.actions) == 1
    assert restored.actions[0].action == "RAISE"
    assert restored.actions[0].raise_to_bb == 2.2
    assert restored._next_sequence == 2

    restored.add_action(
        "hero",
        "CALL",
        amount_bb=1.2,
        ts=1_700_000_002.0,
    )

    store.save(restored)
    final = store.load()

    assert len(final.actions) == 2
    assert final.actions[1].sequence == 2

    rendered = store.text_path.read_text()

    assert "BTN (Alice) raises to 2.2 BB" in rendered
    assert "BB (Hero) calls 1.2 BB" in rendered

    print(rendered)

    last_json = root / "last_completed_canonical_hand.json"
    last_text = root / "last_completed_hand.txt"

    archived = store.archive(
        history_dir=root / "history",
        last_json_path=last_json,
        last_text_path=last_text,
    )

    assert archived.exists()
    assert last_json.exists()
    assert last_text.exists()

    assert last_json.read_text() == store.json_path.read_text()
    assert last_text.read_text() == store.text_path.read_text()

print("CanonicalHandStore smoke test passed.")
