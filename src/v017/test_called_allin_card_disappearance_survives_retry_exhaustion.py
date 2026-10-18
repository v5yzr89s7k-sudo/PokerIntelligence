"""
Regression for Oct 17 live called-all-in failure.

Once one player is independently confirmed all-in, the only remaining
actionable opponent's retained card disappearance must not become FOLD
merely because quantitative retry ownership expires.
"""

from src.v017.frame_hand_observer import FrameHandObserver


def main():
    players = [
        {
            "seat": "sb",
            "position": "SB",
            "name": "SB",
            "stack_bb": 50.0,
            "dealt_in": True,
        },
        {
            "seat": "allin",
            "position": "BTN",
            "name": "AllIn",
            "stack_bb": 26.0,
            "dealt_in": True,
        },
        {
            "seat": "caller",
            "position": "BB",
            "name": "Caller",
            "stack_bb": 41.0,
            "dealt_in": True,
        },
    ]

    observer = FrameHandObserver(
        players=players,
        action_order=["allin", "sb", "caller"],
        small_blind_seat="sb",
        big_blind_seat="caller",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "sb": 49.5,
            "allin": 26.0,
            "caller": 40.0,
        },
        opponent_seats=[
            "sb",
            "allin",
            "caller",
        ],
        quantitative_seats=[
            "allin",
            "caller",
        ],
        hero_seat=None,
        hand_id="called-allin-disappearance-exhaustion",
    )

    # Produce the required state through HandEngine authority.
    # BTN is the authoritative first actor and moves all-in.
    assert observer.hand.next_actor == "allin", (
        observer.hand.next_actor
    )

    assert observer.hand.observe_stack_commitment(
        "allin",
        26.0,
        all_in_confirmed=True,
    )

    assert observer.hand.players["allin"].all_in is True

    # SB is next and leaves the confrontation.
    assert observer.hand.next_actor == "sb", (
        observer.hand.next_actor
    )

    assert observer.hand.observe_fold("sb")

    # Caller is now the only remaining actionable opponent.
    assert observer.hand.next_actor == "caller", (
        observer.hand.next_actor
    )

    # Caller shows physical card disappearance while its stack
    # settlement is still owned by the quantitative lane.
    observer.quantitative_retry_pending["caller"] = {
        "attempts": 7,
        "first_frame": 110,
        "last_frame": 116,
        "commitment_seen": False,
        "reason": "stack_motion",
    }

    # Reproduce the retained physical evidence that existed in the
    # live failure before Caller reached the authoritative frontier.
    observer._retain_pending_card_disappearance(
        "caller",
        frame_id=111,
        physical_type="OPPONENT_CARDS_DISAPPEARED",
    )

    assert observer.pending_card_disappearances, (
        "card disappearance was not retained"
    )

    # Quantitative retries now exhaust without a readable final stack.
    observer.quantitative_retry_pending.pop(
        "caller",
        None,
    )
    observer.quantitative_confirmation_pending.pop(
        "caller",
        None,
    )

    before = list(
        observer.hand.semantic_actions()
    )

    observer.reconcile_pending_card_disappearances()

    after = list(
        observer.hand.semantic_actions()
    )

    assert after == before, (
        "RED: retry exhaustion fabricated FOLD "
        "during called-all-in race"
    )

    assert observer.pending_card_disappearances, (
        "RED: called-all-in physical evidence was discarded"
    )

    assert not observer.hand.players["caller"].folded, (
        "RED: caller was incorrectly folded"
    )

    assert observer.hand.next_actor == "caller"

    print(
        "CALLED-ALL-IN RETRY EXHAUSTION "
        "CANNOT FABRICATE FOLD: PASS"
    )


if __name__ == "__main__":
    main()
