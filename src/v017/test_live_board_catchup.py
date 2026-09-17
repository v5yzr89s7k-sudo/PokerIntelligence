from src.v017.run_live_observer import (
    admit_board_catchup,
)
from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "SB",
        "name": "Hero",
        "stack_bb": 50.0,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
    },
]


def make_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={},
        opponent_seats=[],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="board-catchup-contract",
    )

    # Forced blinds already exist in HandEngine.
    #
    # Hero SB completes to 1 BB.
    # BB is already at the 1 BB price and checks.
    assert (
        observer.hand.observe_stack_commitment(
            "hero",
            0.5,
        )
        == "CALL"
    )

    assert (
        observer.hand.observe_no_commitment(
            "bb"
        )
        == "CHECK"
    )

    assert observer.hand.next_actor is None
    assert observer.hand.street == "PREFLOP"

    return observer


def main():
    board = [
        "2h",
        "9c",
        "Ts",
        "Td",
        "7s",
    ]

    observer = make_observer()

    emitted = admit_board_catchup(
        observer,
        frame_id=100,
        board=board,
    )

    print(
        "final street =",
        observer.hand.street,
    )

    print(
        "final board =",
        observer.hand.board,
    )

    admitted = [
        event
        for event in emitted
        if (
            event.get("type")
            == "STREET_BOUNDARY_ADMITTED"
        )
    ]

    print(
        "admitted streets =",
        [
            event.get("street")
            for event in admitted
        ],
    )

    print(
        "admitted counts =",
        [
            event.get("board_count")
            for event in admitted
        ],
    )

    assert observer.hand.street == "RIVER"
    assert observer.hand.board == board

    assert [
        event["street"]
        for event in admitted
    ] == [
        "FLOP",
        "TURN",
        "RIVER",
    ]

    assert [
        event["board_count"]
        for event in admitted
    ] == [
        3,
        4,
        5,
    ]

    # One delayed five-card identity must preserve exact
    # chronological street ownership.
    assert [
        event["type"]
        for event in admitted
    ] == [
        "STREET_BOUNDARY_ADMITTED",
        "STREET_BOUNDARY_ADMITTED",
        "STREET_BOUNDARY_ADMITTED",
    ]

    print()
    print(
        "V0.17 LIVE BOARD CATCHUP: PASS"
    )


if __name__ == "__main__":
    main()
