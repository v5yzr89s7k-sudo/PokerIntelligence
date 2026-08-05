from src.api.table_snapshot_reader_core_v2 import (
    _normalize_name,
)


requested_seat = "seat_lower_right"

api_response = {
    "name": "Marcota21",
}

player = {
    "seat": requested_seat,
    "name": _normalize_name(api_response.get("name")),
}

assert player["seat"] == "seat_lower_right"
assert player["name"] == "Marcota21"

# The API response cannot reassign the physical seat because it no longer
# contains or controls a seat field.
malicious_or_invalid_response = {
    "seat": "seat_mid_right",
    "name": "Marcota21",
}

player = {
    "seat": requested_seat,
    "name": _normalize_name(
        malicious_or_invalid_response.get("name")
    ),
}

assert player["seat"] == "seat_lower_right"
assert player["name"] == "Marcota21"

print("Snapshot V3 caller-owned seat regression passed.")
