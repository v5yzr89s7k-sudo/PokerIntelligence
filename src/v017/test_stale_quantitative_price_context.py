"""
Regression: blocked quantitative evidence is owned by the betting
context in which it was observed.

A retained later-actor stack observation may survive predecessor
resolution while current_price_bb is unchanged.

It may not be reinterpreted as a new action after intervening
authoritative aggression changes current_price_bb.
"""

from src.v017.frame_hand_observer import FrameHandObserver


def make_observation(
    *,
    frame,
    seat,
    prior,
    value,
):
    return {
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "frame": frame,
        "seat": seat,
        "prior_value": prior,
        "resolved_value": value,
    }


def main():
    observer = object.__new__(
        FrameHandObserver
    )

    observer.pending_quantitative_evidence = []

    class Player:
        street_commitment_bb = 0.0

    class Hand:
        street = "PREFLOP"
        current_price_bb = 1.0
        next_actor = "utg"
        pending_to_act = [
            "utg",
            "hero",
            "villain",
        ]
        actions = []
        players = {
            "utg": Player(),
            "hero": Player(),
            "villain": Player(),
        }

    observer.hand = Hand()

    observation = make_observation(
        frame=83,
        seat="villain",
        prior=98.03,
        value=55.93,
    )

    observer._retain_blocked_quantitative_evidence(
        observation
    )

    assert len(
        observer.pending_quantitative_evidence
    ) == 1

    retained = (
        observer.pending_quantitative_evidence[0]
    )

    print(
        "retained_price =",
        retained.get(
            "retained_current_price_bb"
        ),
    )

    # Simulate intervening authoritative aggression.
    observer.hand.current_price_bb = 9.0
    observer.hand.next_actor = "villain"
    observer.hand.pending_to_act = [
        "villain",
    ]

    # The retained observation belongs to the old 1 BB
    # betting context and must be retired before admission.
    stale = (
        retained.get(
            "retained_current_price_bb"
        )
        != observer.hand.current_price_bb
    )

    print(
        "current_price =",
        observer.hand.current_price_bb,
    )
    print(
        "stale_after_price_change =",
        stale,
    )

    assert (
        retained.get(
            "retained_current_price_bb"
        )
        == 1.0
    ), (
        "retained quantitative evidence does not "
        "own its observation-time betting price"
    )

    assert stale is True

    print(
        "V0.17 STALE QUANTITATIVE PRICE CONTEXT: PASS"
    )


if __name__ == "__main__":
    main()
