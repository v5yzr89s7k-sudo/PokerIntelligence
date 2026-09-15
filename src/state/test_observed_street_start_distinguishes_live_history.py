from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="observed-street-start",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "villain": "BB",
        },
        started_ts=1.0,
    )


def main():
    # ============================================================
    # CASE A
    #
    # Tracker is constructed while the street already exists.
    # We do NOT know that observation owned the beginning of FLOP.
    #
    # First observed later actor must remain synchronization-only.
    # ============================================================

    midstreet = make_hand()
    midstreet.set_board(
        ["Ac", "7d", "2s"],
        ts=2.0,
    )

    midstreet_tracker = BettingRoundTracker(
        midstreet
    )

    print(
        "midstreet tracker owns street start:",
        getattr(
            midstreet_tracker,
            "observed_street_start_owned",
            None,
        ),
    )

    assert not getattr(
        midstreet_tracker,
        "observed_street_start_owned",
        False,
    ), (
        "observer attached to an already-open street must not "
        "claim ownership of its beginning"
    )

    # ============================================================
    # CASE B
    #
    # Tracker already exists before the physical board transition.
    # The same tracker witnesses PREFLOP -> FLOP.
    #
    # After synchronization with CanonicalHand, it must remember
    # that this observer owns the opening boundary of FLOP.
    # ============================================================

    continuous = make_hand()

    continuous_tracker = BettingRoundTracker(
        continuous
    )

    continuous.set_board(
        ["Ac", "7d", "2s"],
        ts=2.0,
    )

    # Exercise the tracker's normal street synchronization path.
    continuous_tracker._sync_street()

    print(
        "continuous tracker owns street start:",
        getattr(
            continuous_tracker,
            "observed_street_start_owned",
            None,
        ),
    )

    assert getattr(
        continuous_tracker,
        "observed_street_start_owned",
        False,
    ) is True, (
        "RED: tracker that physically spans the board transition "
        "does not preserve ownership of the new street start"
    )

    assert continuous_tracker.street == "FLOP"

    print()
    print(
        "PASS: observed street-start ownership distinguishes "
        "mid-street attachment from continuous observation"
    )


if __name__ == "__main__":
    main()
