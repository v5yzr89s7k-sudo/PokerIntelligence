"""
Regression contract:

A confirmed physical stack transition that is terminally rejected as
below_current_price still establishes the newest physical stack baseline.

It must NOT create a poker action.

Blocked-predecessor evidence is different: it remains retained against its
original baseline and is covered by the existing retention regressions.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


def observation(frame, seat, prior, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": seat,
        "prior": prior,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "candidates": ((value, 1),),
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": round(
            prior - value,
            2,
        ),
    }


def main():
    players = [
        {
            "seat": "btn",
            "name": "BTN",
            "position": "BTN",
            "stack_bb": 50.0,
            "is_hero": True,
        },
        {
            "seat": "sb",
            "name": "SB",
            "position": "SB",
            "stack_bb": 40.0,
        },
        {
            "seat": "bb",
            "name": "BB",
            "position": "BB",
            "stack_bb": 60.0,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=[
            "btn",
            "bb",
        ],
        small_blind_seat="sb",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "btn": 50.0,
            "sb": 40.0,
            "bb": 60.0,
        },
        quantitative_seats=[
            "btn",
            "sb",
            "bb",
        ],
        hero_seat="btn",
        hand_id="terminal-physical-baseline",
    )

    # BTN first establishes a 3 BB authoritative price.
    assert observer.hand.next_actor == "btn"

    raised = observer.admit_quantitative_observation(
        observation(
            9,
            "btn",
            50.0,
            47.0,
        )
    )

    assert raised
    assert observer.hand.current_price_bb == 3.0
    assert observer.hand.next_actor == "bb"
    assert (
        observer.hand.players["bb"].street_commitment_bb
        == 1.0
    )

    before_actions = tuple(
        observer.hand.semantic_actions()
    )

    # BB already owns 1 BB. A further 0.12 BB physical decrease
    # reaches only 1.12 BB total, below the authoritative 3 BB price.
    # It must therefore be rejected semantically while still becoming
    # the newest generic physical stack baseline.
    emitted = observer.admit_quantitative_observation(
        observation(
            10,
            "bb",
            60.0,
            59.88,
        )
    )

    assert emitted == ()

    assert tuple(
        observer.hand.semantic_actions()
    ) == before_actions, (
        "terminal physical baseline advancement "
        "must not create semantic poker action"
    )

    assert observer.trusted_stacks["bb"] == 59.88, (
        observer.trusted_stacks
    )

    # No semantic poker action was created, but the confirmed
    # physical stack value became the newest physical baseline.
    #
    # Hand #2 provides the end-to-end proof that the next real action
    # is subsequently measured from this value.

    print(
        "TERMINAL REJECTED QUANTITATIVE "
        "PHYSICAL BASELINE: PASS"
    )


if __name__ == "__main__":
    main()
