from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "BTN",
        "name": "Hero",
        "starting_stack_bb": 100.0,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "Villain",
        "starting_stack_bb": 100.0,
        "is_hero": False,
    },
]


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={},
        trusted_stacks={},
        opponent_seats=["bb"],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="delayed-board-identity",
    )

    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    observer.hand.observe_no_commitment(
        "bb"
    )

    assert observer.hand.next_actor is None

    observer.admit_street_boundary(
        {
            "frame": 10,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 0,
        },
        action_order=["bb", "hero"],
        board=None,
        complete_pending=True,
    )

    assert observer.hand.street == "FLOP"
    assert observer.hand.board == []

    return observer


def main():
    observer = build_observer()

    # Slow identity arrives after FLOP chronology already exists.
    attached = observer.hand.observe_board_identity(
        ["Qc", "3c", "6c"],
    )

    print("street =", observer.hand.street)
    print("board =", observer.hand.board)
    print("attached =", attached)

    assert observer.hand.street == "FLOP"

    assert observer.hand.board == [
        "Qc",
        "3c",
        "6c",
    ], (
        "delayed FLOP identity was not attached "
        "to already-active FLOP"
    )

    # Idempotent replay of the same identity must be harmless.
    again = observer.hand.observe_board_identity(
        ["Qc", "3c", "6c"],
    )

    assert again == [
        "Qc",
        "3c",
        "6c",
    ]

    # Identity attachment must not advance chronology.
    assert observer.hand.street == "FLOP"

    print("STREET ADVANCED BY IDENTITY: NO")
    print("DELAYED BOARD ATTACHED: PASS")
    print(
        "V0.17 DELAYED BOARD IDENTITY "
        "ATTACHMENT: PASS"
    )


if __name__ == "__main__":
    main()
