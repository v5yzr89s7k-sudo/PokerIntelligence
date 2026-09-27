from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "HJ",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
]


def quantitative(frame, seat, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "resolved": True,
        "resolved_value": value,
    }


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hero",
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
            "hero": 50.0,
            "sb": 20.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "utg",
            "hero",
            "sb",
            "bb",
        ],
        hero_seat="hero",
        hand_id="post-boundary-quantitative-authority",
    )

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "utg"

    boundary = {
        "frame": 13,
        "type": "FLOP_BOUNDARY_PHYSICAL",
        "board_count": 3,
    }

    result = observer.admit_street_boundary(
        boundary,
        action_order=[
            "sb",
            "bb",
            "hero",
        ],
        board=[
            "As",
            "Kd",
            "7c",
        ],
        complete_pending=False,
    )

    assert result == ()
    assert observer.hand.street == "PREFLOP"
    assert observer.pending_street_boundaries

    retained_frame = (
        observer
        .pending_street_boundaries[0]
        ["observation"]["frame"]
    )

    assert retained_frame == 13

    before_actions = list(
        observer.hand.semantic_actions()
    )

    before_stack = (
        observer.trusted_stacks["utg"]
    )

    # This physical stack transition occurs AFTER the already-proven
    # FLOP boundary. It therefore cannot describe UTG's unresolved
    # PREFLOP action.
    admitted = (
        observer.admit_quantitative_observation(
            quantitative(
                20,
                "utg",
                48.0,
            )
        )
    )

    print("boundary_frame =", retained_frame)
    print("evidence_frame =", 20)
    print("admitted =", admitted)
    print(
        "next_actor =",
        observer.hand.next_actor,
    )

    # Required temporal-ownership invariant:
    #
    # post-boundary physical evidence cannot be admitted backward
    # into the unresolved prior semantic street.
    assert admitted == (), (
        "RED: frame-20 quantitative evidence was admitted "
        "backward across physical FLOP frame 13"
    )

    assert (
        observer.hand.semantic_actions()
        == before_actions
    ), (
        "RED: prior-street canonical actions changed from "
        "post-boundary evidence"
    )

    assert (
        observer.trusted_stacks["utg"]
        == before_stack
    ), (
        "RED: semantic quantitative baseline advanced from "
        "post-boundary evidence"
    )

    assert observer.hand.street == "PREFLOP"
    assert observer.hand.next_actor == "utg"

    print(
        "POST-BOUNDARY QUANTITATIVE AUTHORITY: PASS"
    )


if __name__ == "__main__":
    main()
