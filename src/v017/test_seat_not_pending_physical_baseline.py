"""
V0.17 seat-not-pending physical stack baseline regression.

A temporally confirmed stack decrease may arrive after the actor has
already been semantically consumed.

That observation has no betting-action authority, but unlike
chronology-blocked evidence it is physically consumed: it must advance
the trusted physical stack baseline so a later independently observed
terminal stack increase can authenticate an uncalled return.

Contract:

    seat_not_pending decrease:
        semantic action: NO
        physical baseline advance: YES

    blocked chronology:
        physical baseline advance: NO

    later authoritative UNCONTESTED return:
        admitted against the advanced physical baseline
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "BTN",
        "name": "Hero",
        "stack_bb": 97.16,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 95.04,
        "dealt_in": True,
    },
]


def observer():
    return FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {
                "bb": {
                    "card_1": {
                        "x": 0,
                        "y": 0,
                        "width": 10,
                        "height": 10,
                    },
                    "card_2": {
                        "x": 10,
                        "y": 0,
                        "width": 10,
                        "height": 10,
                    },
                },
            },
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 97.16,
            "bb": 95.04,
        },
        opponent_seats=["bb"],
        quantitative_seats=[
            "hero",
            "bb",
        ],
        hero_seat="hero",
        hand_id="seat-not-pending-baseline",
    )


def quantitative(
    frame,
    value,
):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "prior": 97.16,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "raw": [
            {
                "stack_bb": value,
            },
        ],
        "candidates": (
            (value, 1),
        ),
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    obs = observer()

    # Reproduce the relevant state directly:
    # Hero is no longer pending, while the hand itself is not yet
    # terminal. Therefore a new Hero decrease cannot become another
    # betting action.
    obs.hand.pending_to_act = []

    assert obs.hand.next_actor is None

    actions_before = list(
        obs.hand.semantic_actions()
    )

    emitted = obs.admit_quantitative_observation(
        quantitative(
            19,
            95.04,
        )
    )

    print(
        "emitted =",
        emitted,
    )
    print(
        "trusted_after_reject =",
        obs.trusted_stacks["hero"],
    )

    assert emitted == ()

    assert (
        obs.hand.semantic_actions()
        == actions_before
    ), (
        "seat_not_pending observation "
        "invented betting semantics"
    )

    assert (
        obs.trusted_stacks["hero"]
        == 95.04
    ), (
        "confirmed seat_not_pending decrease "
        "did not advance physical stack baseline"
    )

    print(
        "SEAT_NOT_PENDING SEMANTIC ACTION: NO"
    )
    print(
        "SEAT_NOT_PENDING PHYSICAL BASELINE: ADVANCED"
    )
    print(
        "V0.17 SEAT_NOT_PENDING PHYSICAL BASELINE: PASS"
    )


if __name__ == "__main__":
    main()
