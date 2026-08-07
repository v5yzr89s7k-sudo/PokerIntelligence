from src.api.table_snapshot_reader_core_v2 import (
    _cache_player,
)


entry = {
    "name": "poker5068",
    "stack_text": "1.12 BB",
    "stack_bb": 1.12,
}

card = {
    "seat": "hero",
    "occupancy_confidence": 0.99,
}

player = _cache_player(entry, card)

assert player["name"] == "poker5068"
assert player["stack_text"] == ""
assert player["stack_bb"] is None
assert player["is_hero"] is True

print("Snapshot cache identity-only regression passed.")
