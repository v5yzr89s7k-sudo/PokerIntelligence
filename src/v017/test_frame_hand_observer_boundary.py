from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "alpha",
        "position": "SB",
        "name": "A",
        "stack_bb": 20.0,
        "dealt_in": True,
    },
    {
        "seat": "beta",
        "position": "BB",
        "name": "B",
        "stack_bb": 30.0,
        "dealt_in": True,
    },
    {
        "seat": "gamma",
        "position": "BTN",
        "name": "C",
        "stack_bb": 40.0,
        "dealt_in": True,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "gamma",
            "alpha",
            "beta",
        ],
        small_blind_seat="alpha",
        big_blind_seat="beta",
        geometry={
            "hole_cards": {},
        },
        trusted_stacks={
            "alpha": 19.5,
            "beta": 29.0,
        },
        opponent_seats=[
            "beta",
            "gamma",
        ],
        quantitative_seats=[
            "alpha",
            "beta",
        ],
        hero_seat="alpha",
        hand_id="neutral-contract",
    )

    state = observer.snapshot()

    assert state["street"] == "PREFLOP"

    assert (
        state["next_actor"]
        == "gamma"
    )

    assert state[
        "trusted_stacks"
    ] == {
        "alpha": 19.5,
        "beta": 29.0,
    }

    assert state[
        "opponent_seats"
    ] == [
        "beta",
        "gamma",
    ]

    assert state[
        "quantitative_seats"
    ] == [
        "alpha",
        "beta",
    ]

    assert (
        state["hero_seat"]
        == "alpha"
    )

    assert (
        state["action_count"]
        == 2
    )

    assert observer.events == []
    assert observer.publications == []

    # Frame processing is migrated incrementally after G3.1.
    # This bootstrap test deliberately does not require a physical frame.

    print(
        "V0.17 FRAMEHANDOBSERVER BOUNDARY: PASS"
    )


if __name__ == "__main__":
    main()
