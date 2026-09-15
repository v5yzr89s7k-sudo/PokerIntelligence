"""
Translate neutral first-owned-frame card visibility into chronology ownership.

Perception owns:
    which physical seats visibly hold cards now

BettingRoundTracker owns:
    legal action order

Therefore perception must NOT tell the tracker that UTG/LJ/HJ folded.
The tracker may only establish that the exact legal prefix before the
earliest currently visible owned seat predates observer chronology.
"""

from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


POSITIONS = {
    "utg": "UTG",
    "lj": "LJ",
    "hj": "HJ",
    "co": "CO",
    "btn": "BTN",
    "sb": "SB",
    "hero": "BB",
}


def make_tracker():
    players = [
        {
            "seat": seat,
            "name": seat.upper(),
            "stack_bb": 100.0,
            "is_hero": seat == "hero",
            "is_active": True,
        }
        for seat in POSITIONS
    ]

    hand = CanonicalHand().start_hand(
        hand_id="visible-seat-acquisition",
        players=players,
        hero_cards=["Qd", "7c"],
        hero_position="BB",
        positions=POSITIONS,
        started_ts=1.0,
    )

    hand.dealt_in_seats = list(POSITIONS)
    hand.current_street = "PREFLOP"

    return hand, BettingRoundTracker(hand)


def voluntary_actions(hand):
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
    hand, tracker = make_tracker()

    assert hand.players_to_act == [
        "utg",
        "lj",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    # First OWNED frame:
    #
    # UTG/LJ/HJ already absent.
    # CO/BTN/SB visibly still hold cards.
    # Hero is independently known active.
    #
    # The tracker, not perception, must determine that CO is the earliest
    # legal seat represented in the owned visibility set.
    result = tracker.establish_observer_acquisition_from_visible_seats(
        street="PREFLOP",
        visible_seats=[
            "co",
            "btn",
            "sb",
        ],
        hero_owned=True,
        ts=10.0,
    )

    assert result is not None

    assert result["first_owned_seat"] == "co"
    assert result["pre_acquisition_seats"] == [
        "utg",
        "lj",
        "hj",
    ]

    assert hand.players_to_act == [
        "co",
        "btn",
        "sb",
        "hero",
    ]

    # Absolutely no poker action semantics may be manufactured.
    assert voluntary_actions(hand) == []

    for seat in ("utg", "lj", "hj"):
        player = hand.players[seat]
        assert player.folded is False
        assert player.active is True

    # --------------------------------------------------------------
    # Empty opponent visibility is insufficient unless Hero itself is
    # the first known owned live obligation.
    # --------------------------------------------------------------
    hand2, tracker2 = make_tracker()

    result2 = tracker2.establish_observer_acquisition_from_visible_seats(
        street="PREFLOP",
        visible_seats=[],
        hero_owned=False,
        ts=10.0,
    )

    assert result2 is None
    assert hand2.players_to_act == [
        "utg",
        "lj",
        "hj",
        "co",
        "btn",
        "sb",
        "hero",
    ]

    # --------------------------------------------------------------
    # Hero can participate as an owned seat without perception inventing
    # an opponent seat. If Hero is the only owned live seat, the exact
    # legal prefix may predate acquisition.
    # --------------------------------------------------------------
    hand3, tracker3 = make_tracker()

    result3 = tracker3.establish_observer_acquisition_from_visible_seats(
        street="PREFLOP",
        visible_seats=[],
        hero_owned=True,
        ts=10.0,
    )

    assert result3["first_owned_seat"] == "hero"
    assert result3["pre_acquisition_seats"] == [
        "utg",
        "lj",
        "hj",
        "co",
        "btn",
        "sb",
    ]

    assert hand3.players_to_act == [
        "hero",
    ]

    assert voluntary_actions(hand3) == []

    print(
        "PASS visible-seat acquisition translation: "
        "perception supplies visibility; betting order owns prefix"
    )


if __name__ == "__main__":
    main()
