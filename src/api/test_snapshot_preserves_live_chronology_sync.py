from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def main():
    positions = {
        "utg": "UTG",
        "hj": "HJ",
        "co": "CO",
        "btn": "BTN",
        "sb": "SB",
        "hero": "BB",
    }

    players = [
        {
            "seat": seat,
            "name": seat.upper(),
            "stack_bb": 50.0,
            "is_hero": seat == "hero",
            "is_active": True,
        }
        for seat in (
            "utg",
            "hj",
            "co",
            "btn",
            "sb",
            "hero",
        )
    ]

    hand = CanonicalHand().start_hand(
        hand_id="snapshot-chronology-regression",
        players=players,
        hero_cards=["2c", "9s"],
        hero_position="BB",
        positions=positions,
        started_ts=1.0,
    )

    tracker = BettingRoundTracker(hand)

    original_queue = list(
        hand.players_to_act
    )

    # A later actor by itself has no authority to consume predecessor
    # obligations or manufacture predecessor actions.
    added = tracker.advance_to_observed_actor(
        "co",
        blocked_seats=set(),
        ts=2.0,
    )

    assert added == []

    assert hand.players_to_act == original_queue, (
        "later actor observation consumed unresolved predecessor "
        f"obligations: {hand.players_to_act}"
    )

    # Observation ownership is a separate explicit transaction.
    #
    # UTG/HJ are known to predate this observer's acquisition boundary.
    # Releasing them from the live obligation queue does not claim that
    # either player folded, checked, called, raised, or otherwise acted.
    frontier = (
        tracker.establish_observer_acquisition_frontier(
            street="PREFLOP",
            first_owned_seat="co",
            pre_acquisition_seats=[
                "utg",
                "hj",
            ],
            ts=2.0,
        )
    )

    synchronized_queue = list(
        hand.players_to_act
    )

    assert synchronized_queue == [
        "co",
        "btn",
        "sb",
        "hero",
    ], synchronized_queue

    assert frontier[
        "pre_acquisition_seats"
    ] == [
        "utg",
        "hj",
    ]

    forced_actions = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    assert not any(
        action.street == "PREFLOP"
        and action.action not in forced_actions
        for action in hand.actions
    ), (
        "observer acquisition manufactured voluntary "
        "predecessor semantics"
    )

    snapshot_players = [
        {
            **player,
            "name": (
                f"SNAPSHOT_{player['seat']}"
            ),
        }
        for player in players
    ]

    # Asynchronous table_snapshot is enrichment only. It must preserve
    # the already-established observer-owned chronology frontier.
    hand.update_table_snapshot(
        players=snapshot_players,
        hero_position="BB",
        positions=positions,
        dealt_in_seats=list(positions),
    )

    after_snapshot_queue = list(
        hand.players_to_act
    )

    print(
        "original_queue:",
        original_queue,
    )
    print(
        "owned_queue:",
        synchronized_queue,
    )
    print(
        "after_snapshot_queue:",
        after_snapshot_queue,
    )

    assert (
        after_snapshot_queue
        == synchronized_queue
    ), (
        "RED: asynchronous table_snapshot erased the "
        "observer acquisition chronology frontier: "
        f"before_snapshot={synchronized_queue} "
        f"after_snapshot={after_snapshot_queue}"
    )

    assert not any(
        action.street == "PREFLOP"
        and action.action not in forced_actions
        for action in hand.actions
    ), (
        "snapshot enrichment manufactured voluntary "
        "predecessor semantics"
    )

    print(
        "PASS: asynchronous table_snapshot preserves "
        "explicit observer acquisition chronology without "
        "manufacturing predecessor actions"
    )


if __name__ == "__main__":
    main()
