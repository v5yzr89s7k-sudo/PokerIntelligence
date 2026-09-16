"""
G3.5A real-frame regression.

Raw July 22 screenshots must cause FrameHandObserver.process_frame()
to emit the independently established physical street boundaries.

This test deliberately disables quantitative stack seats so that it
isolates physical board/street perception. Board count itself is real
pixel perception through count_board_cards(); it is not mocked.

No board identity artifact, expected action sequence, or legacy
semantic engine is used.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)

from src.v017.july22_frame_preflop_replay import (
    ACTION_ORDER,
    GEOMETRY,
    PLAYERS,
    TRACKED_STACKS,
    load_frame,
)


OPPONENT_SEATS = [
    "seat_upper_left",
    "seat_upper_right",
    "seat_mid_right",
    "seat_lower_right",
    "seat_lower_left",
]


EXPECTED = [
    (
        52,
        "FLOP_BOUNDARY_PHYSICAL",
        3,
    ),
    (
        103,
        "TURN_BOUNDARY_PHYSICAL",
        4,
    ),
    (
        115,
        "RIVER_BOUNDARY_PHYSICAL",
        5,
    ),
]


def build_observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=ACTION_ORDER,
        small_blind_seat="hero",
        big_blind_seat="seat_lower_left",
        geometry=GEOMETRY,
        trusted_stacks=dict(
            TRACKED_STACKS
        ),
        opponent_seats=OPPONENT_SEATS,

        # G3.5A isolation:
        # do not invoke targeted stack OCR.
        quantitative_seats=[],

        hero_seat="hero",
        hand_id="july22-g3.5a-real-frames",
    )


def main():
    observer = build_observer()

    initial_street = observer.hand.street
    initial_actions = list(
        observer.hand.actions
    )
    initial_next_actor = (
        observer.hand.next_actor
    )
    initial_trusted_stacks = dict(
        observer.trusted_stacks
    )

    boundaries = []

    for number in range(1, 136):
        frame = load_frame(number)

        result = observer.process_frame(
            frame,
            frame_id=number,
        )

        for event in result.events:
            if event["type"].endswith(
                "_BOUNDARY_PHYSICAL"
            ):
                boundaries.append(
                    (
                        int(event["frame"]),
                        event["type"],
                        int(event["board_count"]),
                    )
                )

    print("===== REAL FRAME BOUNDARIES =====")
    for row in boundaries:
        print(row)

    assert boundaries == EXPECTED, (
        "real-frame physical boundary mismatch: "
        f"observed={boundaries} "
        f"expected={EXPECTED}"
    )

    # process_frame must remain perception-only.
    assert observer.hand.street == initial_street
    assert observer.hand.actions == initial_actions
    assert (
        observer.hand.next_actor
        == initial_next_actor
    )

    # With quantitative perception disabled, no trusted
    # quantitative state may move either.
    assert (
        observer.trusted_stacks
        == initial_trusted_stacks
    )

    print()
    print(
        "semantic street:",
        observer.hand.street,
    )
    print(
        "semantic action count:",
        len(observer.hand.actions),
    )
    print(
        "next actor:",
        observer.hand.next_actor,
    )
    print()
    print(
        "G3.5A JULY22 REAL-FRAME "
        "STREET BOUNDARIES: PASS"
    )


if __name__ == "__main__":
    main()
