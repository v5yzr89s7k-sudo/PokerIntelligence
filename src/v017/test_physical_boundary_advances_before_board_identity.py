from src.v017.frame_hand_observer import FrameHandObserver


def build_observer():
    players = [
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

    observer = FrameHandObserver(
        players=players,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={},
        trusted_stacks={},
        opponent_seats=["bb"],
        quantitative_seats=[],
        hero_seat="hero",
        hand_id="physical-boundary-fast-path",
    )

    # Close PREFLOP legally.
    observer.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    observer.hand.observe_no_commitment("bb")

    assert observer.hand.next_actor is None
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.board == []

    return observer


def main():
    observer = build_observer()

    boundary = {
        "frame": 10,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
        "previous_board_count": 0,
    }

    # Physical board progression owns street chronology.
    # Card identities are intentionally unresolved here.
    observer.admit_street_boundary(
        boundary,
        action_order=["bb", "hero"],
        board=None,
        complete_pending=True,
    )

    print("street =", observer.hand.street)
    print("board =", observer.hand.board)
    print("next_actor =", observer.hand.next_actor)

    assert observer.hand.street == "FLOP", (
        "physical FLOP boundary did not immediately "
        "establish FLOP authority"
    )

    assert observer.hand.board == [], (
        "physical street authority invented board identity"
    )

    assert observer.hand.next_actor == "bb"

    print("BOARD IDENTITY REQUIRED FOR STREET: NO")
    print("BOARD IDENTITY INVENTED: NO")
    print("POST-BOUNDARY SEMANTIC STREET: FLOP")
    print(
        "V0.17 PHYSICAL STREET AUTHORITY "
        "BEFORE BOARD IDENTITY: PASS"
    )


if __name__ == "__main__":
    main()
