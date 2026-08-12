from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


POSITIONS = {
    "seat_upper_left": "UTG",
    "seat_top": "UTG+1",
    "seat_mid_right": "HJ",
    "seat_lower_right": "CO",
    "hero": "BTN",
    "seat_lower_left": "SB",
    "seat_mid_left": "BB",
}


def inferred(
    episode_id,
    seat,
    action,
    *,
    street,
    delta_bb=None,
    ts=None,
):
    measurements = {}

    if delta_bb is not None:
        measurements["stack_change"] = {
            "delta_bb": delta_bb,
        }

    return {
        "episode_id": episode_id,
        "seat": seat,
        "street": street,
        "action": action,
        "confidence": 0.95,
        "measurements": measurements,
        "evidence": (
            ["stack_changed", "bet_region_occupied"]
            if delta_bb is not None
            else []
        ),
        "ts": (
            float(ts)
            if ts is not None
            else float(episode_id)
        ),
    }


def make_hand():
    players = [
        {
            "seat": seat,
            "name": seat,
            "stack_bb": 100.0,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="replay-0001-complete",
        players=players,
        hero_cards=["6c", "8d"],
        hero_position="BTN",
        positions=POSITIONS,
    )

    hand.dealt_in_seats = list(POSITIONS)

    for seat in POSITIONS:
        hand.add_action(
            seat=seat,
            action="POST_ANTE",
            amount_bb=0.125,
            confidence=1.0,
            source="replay_0001_seed",
        )

    hand.add_action(
        seat="seat_lower_left",
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.add_action(
        seat="seat_mid_left",
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="replay_0001_seed",
    )

    hand.current_bet_bb = 1.0

    hand.players_to_act = [
        "seat_upper_left",
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
        "hero",
        "seat_lower_left",
        "seat_mid_left",
    ]

    return hand


def voluntary(hand):
    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    return [
        action
        for action in hand.actions
        if action.action not in forced
    ]


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # --------------------------------------------------------
    # PREFLOP
    #
    # Observed Hero open resolves all preceding non-committing
    # players as folds.
    # --------------------------------------------------------

    hero_open = tracker.ingest(
        inferred(
            1,
            "hero",
            "BET_OR_RAISE",
            street="PREFLOP",
            delta_bb=3.5,
            ts=1.0,
        )
    )

    assert hero_open is not None
    assert hero_open.action == "RAISE"
    assert hero_open.raise_to_bb == 3.5

    # BB's observed 9 BB stack decrease is additional money:
    # prior live BB = 1, therefore raise-to = 10.
    bb_three_bet = tracker.ingest(
        inferred(
            2,
            "seat_mid_left",
            "CALL_OR_RAISE",
            street="PREFLOP",
            delta_bb=9.0,
            ts=2.0,
        )
    )

    assert bb_three_bet is not None
    assert bb_three_bet.action == "RAISE"
    assert bb_three_bet.raise_to_bb == 10.0

    # Hero had 3.5 live and adds 6.5, exactly matching 10.
    hero_call = tracker.ingest(
        inferred(
            3,
            "hero",
            "CALL_OR_RAISE",
            street="PREFLOP",
            delta_bb=6.5,
            ts=3.0,
        )
    )

    assert hero_call is not None
    assert hero_call.action == "CALL"
    assert hero_call.amount_bb == 6.5

    # --------------------------------------------------------
    # FLOP
    # --------------------------------------------------------

    hand.set_board(
        ["Ad", "3d", "3c"],
        ts=4.0,
    )

    hand.players_to_act = [
        "seat_mid_left",
        "hero",
    ]

    # BB's real Replay transition was 56.6 -> 51.6.
    bb_bet = tracker.ingest(
        inferred(
            4,
            "seat_mid_left",
            "BET_OR_RAISE",
            street="FLOP",
            delta_bb=5.0,
            ts=5.0,
        )
    )

    assert bb_bet is not None
    assert bb_bet.action == "BET"
    assert bb_bet.amount_bb == 5.0

    # Dedicated Hero fold event ultimately canonicalizes to FOLD.
    hero_fold = hand.add_action(
        seat="hero",
        action="FOLD",
        confidence=1.0,
        source="hero_fold",
        ts=6.0,
    )

    assert hero_fold is not None

    # --------------------------------------------------------
    # COMPLETE CHRONOLOGY
    # --------------------------------------------------------

    actions = voluntary(hand)

    actual = [
        (
            action.street,
            action.position,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in actions
    ]

    expected = [
        ("PREFLOP", "UTG",   "FOLD",  None, None),
        ("PREFLOP", "UTG+1", "FOLD",  None, None),
        ("PREFLOP", "HJ",    "FOLD",  None, None),
        ("PREFLOP", "CO",    "FOLD",  None, None),
        ("PREFLOP", "BTN",   "RAISE", None, 3.5),
        ("PREFLOP", "SB",    "FOLD",  None, None),
        ("PREFLOP", "BB",    "RAISE", None, 10.0),
        ("PREFLOP", "BTN",   "CALL",  6.5, None),
        ("FLOP",    "BB",    "BET",   5.0, None),
        ("FLOP",    "BTN",   "FOLD",  None, None),
    ]

    print("===== REPLAY 0001 COMPLETE ACTION HISTORY =====")

    for item in actual:
        print(item)

    assert actual == expected, (
        "\nACTUAL:\n"
        + "\n".join(map(str, actual))
        + "\n\nEXPECTED:\n"
        + "\n".join(map(str, expected))
    )

    assert hand.players["hero"].folded is True
    assert hand.players["hero"].active is False

    print()
    print(
        "PASS Replay 0001 complete hand: "
        "full chronological action history preserved"
    )


if __name__ == "__main__":
    main()
