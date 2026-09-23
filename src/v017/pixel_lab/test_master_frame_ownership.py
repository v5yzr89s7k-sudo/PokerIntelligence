from src.v017.pixel_lab.master_frame import (
    BOARD_SLOTS,
    SEATS,
    MasterFrame,
    required_ownership,
)


def main():
    print(
        "===== MASTER FRAME OWNERSHIP ====="
    )

    required = required_ownership()

    print(
        "required_lanes =",
        len(required),
    )

    frame = MasterFrame()

    print(
        "initial_missing =",
        len(frame.missing()),
    )

    assert (
        len(frame.missing())
        == len(required)
    )

    # An incomplete frame must NEVER be emitted.
    try:
        frame.emit()
    except RuntimeError as exc:
        print(
            "incomplete_emit = BLOCKED"
        )
        print(
            "reason =",
            str(exc)[:180],
        )
    else:
        raise AssertionError(
            "incomplete master frame was emitted"
        )

    for seat in SEATS:
        frame.claim_seat_identity(seat)
        frame.claim_stack(seat)
        frame.claim_hole_cards(seat)
        frame.claim_dealer(seat)
        frame.claim_bet(seat)

    for slot in BOARD_SLOTS:
        frame.claim_board(slot)

    frame.claim_pot()

    missing = frame.missing()

    print(
        "final_missing =",
        missing,
    )

    assert not missing

    image = frame.emit()

    assert image.shape[:2] == (
        2168,
        3456,
    )

    print()
    print(
        "MASTER OWNERSHIP GATE: PASS"
    )


if __name__ == "__main__":
    main()
