from src.v017.frame_hand_observer import FrameHandObserver


def main():
    observer = FrameHandObserver(
        players=[
            {
                "seat": "utg",
                "position": "UTG",
                "name": "UTG",
                "stack_bb": 50.0,
            },
            {
                "seat": "sb",
                "position": "SB",
                "name": "SB",
                "stack_bb": 40.0,
            },
            {
                "seat": "bb",
                "position": "BB",
                "name": "BB",
                "stack_bb": 40.0,
            },
        ],
        action_order=[
            "utg",
            "sb",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "utg": 50.0,
            "sb": 40.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "utg",
            "sb",
            "bb",
        ],
        hero_seat="sb",
        hand_id="blocked-boundary",
    )

    before_actions = list(
        observer.hand.semantic_actions()
    )
    before_events = list(observer.events)

    emitted = observer.admit_street_boundary(
        {
            "frame": 20,
            "type": "FLOP_BOUNDARY_PHYSICAL",
            "board_count": 3,
            "previous_board_count": 0,
        },
        action_order=[
            "sb",
            "bb",
        ],
        board=[
            "Qh",
            "Kh",
            "3d",
        ],
        complete_pending=True,
    )

    assert emitted == ()
    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "utg"
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )
    assert observer.events == before_events

    print(
        "V0.17 BLOCKED STREET BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
