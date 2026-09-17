"""
Live regression:

A later actor's quantitative observation cannot consume or invent an
action for an unresolved predecessor who is still facing a price.

The entire admission must defer without semantic or quantitative
mutation.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "utg",
        "position": "UTG",
        "name": "UTG",
        "stack_bb": None,
    },
    {
        "seat": "hj",
        "position": "HJ",
        "name": "HJ",
        "stack_bb": 50.0,
    },
    {
        "seat": "sb",
        "position": "SB",
        "name": "SB",
        "stack_bb": None,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 40.0,
    },
]


def main():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "utg",
            "hj",
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
            "hj": 50.0,
            "bb": 40.0,
        },
        opponent_seats=[
            "utg",
            "hj",
            "sb",
            "bb",
        ],
        quantitative_seats=[
            "hj",
            "bb",
        ],
        hero_seat="hj",
        hand_id="blocked-predecessor",
    )

    before_actions = list(
        observer.hand.semantic_actions()
    )
    before_events = list(
        observer.events
    )
    before_publications = list(
        observer.publications
    )
    before_stack = observer.trusted_stacks[
        "hj"
    ]

    assert observer.hand.next_actor == "utg"
    assert observer.hand.current_price_bb == 1.0

    emitted = (
        observer.admit_quantitative_observation(
            {
                "frame": 10,
                "type":
                    "STACK_QUANTITATIVE_OBSERVATION",
                "seat": "hj",
                "resolved": True,
                "resolved_value": 48.0,
            }
        )
    )

    assert emitted == ()

    # UTG remains unresolved and authoritative.
    assert observer.hand.next_actor == "utg"

    # No invented UTG fold/check and no later HJ action.
    assert (
        observer.hand.semantic_actions()
        == before_actions
    )

    # Deferred evidence cannot advance trusted quantitative state.
    assert (
        observer.trusted_stacks["hj"]
        == before_stack
    )

    assert observer.events == before_events
    assert (
        observer.publications
        == before_publications
    )

    print(
        "V0.17 BLOCKED QUANTITATIVE "
        "PREDECESSOR: PASS"
    )


if __name__ == "__main__":
    main()
