"""
V0.17 same-actor card/quantitative arbitration regression.

If the current authoritative actor has confirmed physical card
disappearance in the same frame that an in-flight quantitative
candidate settles for that same seat, the quantitative candidate
must not consume the actor before the fold evidence is arbitrated.

This does NOT alter the established different-seat rule where a later
actor's quantitative action may prove predecessor chronology.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 100.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "villain",
        "position": "BB",
        "name": "Villain",
        "stack_bb": 100.0,
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
            "villain",
            "hero",
        ],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 99.5,
            "villain": 99.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=[
            "hero",
            "villain",
        ],
        hero_seat="hero",
        hand_id="same-actor-card-blocks-quantitative",
    )

    assert observer.hand.next_actor == "villain"

    actions_before = list(
        observer.hand.semantic_actions()
    )

    # Production retains card disappearance before processing the
    # quantitative settlement loop for this physical frame.
    observer.retain_card_disappearance(
        "villain",
        frame_id=17,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert (
        observer.pending_card_disappearances
    )

    # Reproduce the live collision: the same current actor also has
    # a settled quantitative candidate in this frame.
    admitted = observer.admit_quantitative_observation(
        quantitative(
            17,
            "villain",
            31.66,
        )
    )

    # Required ownership contract:
    #
    # The same-seat quantitative candidate must not consume Villain
    # as a raise while Villain's same-frame confirmed disappearance
    # is already retained.
    assert admitted == (), (
        "same-actor quantitative candidate consumed actor "
        "before confirmed card disappearance"
    )

    assert observer.hand.current_price_bb == 1.0, (
        "same-actor collision poisoned betting price"
    )

    # Card evidence now owns the actor.
    reconciled = (
        observer.reconcile_pending_card_disappearances()
    )

    assert len(reconciled) == 1

    actions = observer.hand.semantic_actions()

    assert len(actions) == len(actions_before) + 1

    last = actions[-1]

    assert last["seat"] == "villain"
    assert last["action"] == "FOLD"

    assert observer.hand.current_price_bb == 1.0

    print("SAME ACTOR QUANTITATIVE ADMITTED: NO")
    print("BETTING PRICE POISONED: NO")
    print("CONFIRMED CARD DISAPPEARANCE -> FOLD: PASS")
    print("V0.17 SAME-ACTOR CARD/QUANTITATIVE ARBITRATION: PASS")


if __name__ == "__main__":
    main()
