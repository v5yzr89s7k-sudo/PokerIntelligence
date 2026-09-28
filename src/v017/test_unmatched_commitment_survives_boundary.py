from src.v017.hand_engine import HandEngine


def main():
    players = [
        {
            "seat": "hero",
            "position": "CO",
            "name": "Hero",
            "dealt_in": True,
        },
        {
            "seat": "bb",
            "position": "BB",
            "name": "Villain",
            "dealt_in": True,
        },
    ]

    hand = HandEngine(
        players=players,
        action_order=["hero", "bb"],
        small_blind_seat="hero",
        big_blind_seat="bb",
        small_blind_bb=0.5,
        big_blind_bb=1.0,
    )

    # Reproduce the accounting condition directly:
    # Hero has 2.12 BB more committed than Villain.
    hand.players["hero"].street_commitment_bb = 4.12
    hand.players["bb"].street_commitment_bb = 2.0

    # Betting round is closed so a street transition is legal.
    hand.pending_to_act = []

    before = hand.unmatched_commitment_bb("hero")

    print("unmatched_before_boundary =", before)

    assert before == 2.12

    hand.start_street(
        "FLOP",
        ["hero", "bb"],
        board=["Jd", "9s", "Tc"],
    )

    after = hand.unmatched_commitment_bb("hero")

    print("unmatched_after_boundary =", after)

    assert after == 2.12, (
        "authoritative unmatched commitment was destroyed "
        "by street transition"
    )

    print("UNMATCHED COMMITMENT SURVIVES BOUNDARY: PASS")


if __name__ == "__main__":
    main()
