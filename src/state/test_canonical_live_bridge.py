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
        hand_id="bridge-test",
        players=[],
        hero_cards=["Jh", "Jd"],
        hero_position="unknown",
        positions={},
        started_ts=1_700_000_000.0,
    )
    store.save(hand)

    restored = store.load()
    restored.update_table_snapshot(
        players=[
            {
                "seat": "seat_mid_left",
                "name": "Villain",
                "stack_bb": 25.0,
                "is_hero": False,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 31.0,
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_position="BB",
        positions={
            "seat_mid_left": "BTN",
            "hero": "BB",
        },
    )
    restored.set_board(["Ah", "7c", "2d"])
    store.save(restored)

    final = store.load()

    assert final.hero_cards == ["Jh", "Jd"]
    assert final.hero_position == "BB"
    assert final.players["hero"].name == "Hero"
    assert final.players["seat_mid_left"].position == "BTN"
    assert final.board == ["Ah", "7c", "2d"]
    assert final.current_street == "FLOP"

    text = store.text_path.read_text()

    assert "TABLE — 2 players" in text
    assert "Hero Cards: Jh Jd" in text
    assert "FLOP: Ah 7c 2d" in text

    print(text)

print("Canonical live-bridge smoke test passed.")
