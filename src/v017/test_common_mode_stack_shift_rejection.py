from src.v017.frame_hand_observer import (
    common_mode_stack_shift_seats,
)


def main():
    print(
        "===== COMMON-MODE STACK SHIFT CONTRACT ====="
    )

    observations = [
        {
            "seat": "seat_top",
            "prior": 30.25,
            "resolved_value": 30.15,
        },
        {
            "seat": "seat_upper_right",
            "prior": 19.17,
            "resolved_value": 19.07,
        },
        {
            "seat": "seat_mid_right",
            "prior": 31.27,
            "resolved_value": 31.17,
        },
        {
            "seat": "seat_lower_right",
            "prior": 17.46,
            "resolved_value": 17.36,
        },
        {
            "seat": "seat_lower_left",
            "prior": 5.28,
            "resolved_value": 5.18,
        },
    ]

    rejected = common_mode_stack_shift_seats(
        observations
    )

    print("rejected =", sorted(rejected))

    assert rejected == {
        "seat_top",
        "seat_upper_right",
        "seat_mid_right",
        "seat_lower_right",
        "seat_lower_left",
    }

    # A genuine isolated commitment must survive.
    observations = [
        {
            "seat": "seat_top",
            "prior": 30.25,
            "resolved_value": 28.25,
        },
        {
            "seat": "seat_upper_right",
            "prior": 21.17,
            "resolved_value": 21.17,
        },
        {
            "seat": "seat_mid_right",
            "prior": 31.27,
            "resolved_value": 31.27,
        },
    ]

    rejected = common_mode_stack_shift_seats(
        observations
    )

    assert rejected == set(), rejected

    # Two matching movements are not sufficient to declare
    # table-wide common-mode corruption.
    observations = [
        {
            "seat": "seat_top",
            "prior": 30.25,
            "resolved_value": 30.15,
        },
        {
            "seat": "seat_upper_right",
            "prior": 21.17,
            "resolved_value": 21.07,
        },
        {
            "seat": "seat_mid_right",
            "prior": 31.27,
            "resolved_value": 31.27,
        },
    ]

    rejected = common_mode_stack_shift_seats(
        observations
    )

    assert rejected == set(), rejected

    print(
        "V0.17 COMMON-MODE STACK SHIFT "
        "CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
