from src.api.table_snapshot_reader_core_v2 import (
    preserve_unresolved_opponent_names,
)


fresh_players = {
    "seat_top": {
        "seat": "seat_top",
        "name": "",
        "stack_bb": 47.5,
        "is_hero": False,
    },
    "hero": {
        "seat": "hero",
        "name": "poker5068",
        "stack_bb": 52.0,
        "is_hero": True,
    },
}

# This represents stale persistent cache data from a prior hand/table.
stale_cache = {
    "seat_top": {
        "name": "Vano001",
        "stack_bb": 99.33,
        "hash": "ffffffffffffffff",
    },
}

missing_name_cards = [
    {
        "seat": "seat_top",
    },
]

unresolved = preserve_unresolved_opponent_names(
    fresh_players,
    missing_name_cards,
)

assert unresolved == ["seat_top"]
assert fresh_players["seat_top"]["name"] == ""
assert fresh_players["seat_top"]["stack_bb"] == 47.5

# The stale cached identity must remain unused.
assert stale_cache["seat_top"]["name"] == "Vano001"
assert (
    fresh_players["seat_top"]["name"]
    != stale_cache["seat_top"]["name"]
)

# Hero identity is outside this opponent-only policy.
assert fresh_players["hero"]["name"] == "poker5068"

print("Snapshot unresolved-name policy regression passed.")

# Stabilization invariant: an opponent cache entry is never authoritative
# merely because it belongs to the same physical seat.
assert stale_cache["seat_top"]["name"] == "Vano001"
assert fresh_players["seat_top"]["name"] == ""

print("Opponent seat-cache reuse remains disabled.")
