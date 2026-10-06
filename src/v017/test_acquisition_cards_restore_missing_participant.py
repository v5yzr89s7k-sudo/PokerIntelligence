from src.events.detectors.card_presence import SEAT_ORDER

stack_frozen = (
    "seat_top",
    "seat_mid_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
)

card_participants = {
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
}

merged = tuple(
    seat
    for seat in SEAT_ORDER
    if seat in (
        set(stack_frozen)
        | card_participants
    )
)

assert merged == (
    "seat_top",
    "seat_upper_right",
    "seat_mid_right",
    "hero",
    "seat_lower_left",
    "seat_mid_left",
    "seat_upper_left",
), merged

assert len(merged) == 7

print("ACQUISITION CARD PARTICIPANT RESTORATION: PASS")
print("final =", merged)
