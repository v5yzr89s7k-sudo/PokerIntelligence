from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def make_hand(street="PREFLOP"):
    players = [
        {
            "seat": "seat_top",
            "name": "P1",
            "stack_bb": 50,
        },
        {
            "seat": "seat_upper_right",
            "name": "P2",
            "stack_bb": 50,
        },
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 50,
        },
    ]

    positions = {
        "seat_top": "UTG",
        "seat_upper_right": "HJ",
        "hero": "BTN",
    }

    hand = CanonicalHand().start_hand(
        hand_id=f"test-{street.lower()}",
        players=players,
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions=positions,
    )

    hand.dealt_in_seats = list(
        positions
    )

    if street == "FLOP":
        hand.set_board(
            ["2c", "7d", "Jh"],
            ts=1.0,
        )

    hand.players_to_act = [
        "seat_top",
        "seat_upper_right",
        "hero",
    ]

    return hand


def actions(hand, street=None):
    result = []

    for action in hand.actions:
        if (
            street is not None
            and action.street != street
        ):
            continue

        result.append(
            (
                action.seat,
                action.action,
            )
        )

    return result


def test_quantitative_action_does_not_infer_predecessors():
    """
    Quantitative evidence identifies one actor's commitment.

    It is not chronology evidence for earlier seats.

    If Hero is observed quantitatively while earlier actors still
    precede Hero in players_to_act, the episode must defer without
    synthesizing folds or mutating the queue.
    """
    hand = make_hand()

    hand.current_bet_bb = 1.0

    tracker = BettingRoundTracker(
        hand
    )

    before = list(
        hand.players_to_act
    )

    result = tracker.ingest({
        "episode_id": 1,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.5,
            }
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    assert result is None

    assert actions(hand) == []

    assert (
        hand.players_to_act
        == before
    )

    assert (
        1
        not in tracker.processed_episode_ids
    )


def test_actor_chronology_then_quantitative_preflop():
    """
    Physical actor chronology owns skipped-seat resolution.

    Once chronology advances to Hero, the previously unresolved
    predecessors may be inferred passive and Hero's quantitative
    action becomes admissible.
    """
    hand = make_hand()

    hand.current_bet_bb = 1.0

    tracker = BettingRoundTracker(
        hand
    )

    added = (
        tracker.advance_to_observed_actor(
            "hero",
            ts=1.5,
            blocked_seats=[],
        )
    )

    assert [
        (
            action.seat,
            action.action,
        )
        for action in added
    ] == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", "FOLD"),
    ]

    assert hand.players_to_act == [
        "hero"
    ]

    result = tracker.ingest({
        "episode_id": 2,
        "seat": "hero",
        "street": "PREFLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 2.5,
            }
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    assert result is not None

    assert actions(hand) == [
        ("seat_top", "FOLD"),
        ("seat_upper_right", "FOLD"),
        ("hero", "RAISE"),
    ]


def test_actor_chronology_then_quantitative_postflop():
    """
    With no open postflop bet, physical chronology may prove
    skipped predecessors checked. The later quantitative actor
    is then processed normally.
    """
    hand = make_hand(
        "FLOP"
    )

    hand.current_bet_bb = 0.0

    tracker = BettingRoundTracker(
        hand
    )

    added = (
        tracker.advance_to_observed_actor(
            "hero",
            ts=1.5,
            blocked_seats=[],
        )
    )

    assert [
        (
            action.seat,
            action.action,
        )
        for action in added
    ] == [
        ("seat_top", "CHECK"),
        ("seat_upper_right", "CHECK"),
    ]

    result = tracker.ingest({
        "episode_id": 3,
        "seat": "hero",
        "street": "FLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.0,
            }
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    assert result is not None

    assert actions(
        hand,
        "FLOP",
    ) == [
        ("seat_top", "CHECK"),
        ("seat_upper_right", "CHECK"),
        ("hero", "BET"),
    ]


def test_blocker_prevents_passive_skip():
    """
    Physical chronology itself is not permission to cross
    unresolved commitment evidence.

    A blocked predecessor keeps both chronology and the later
    quantitative action unresolved.
    """
    hand = make_hand(
        "FLOP"
    )

    hand.current_bet_bb = 0.0

    tracker = BettingRoundTracker(
        hand
    )

    before = list(
        hand.players_to_act
    )

    added = (
        tracker.advance_to_observed_actor(
            "hero",
            ts=1.5,
            blocked_seats=[
                "seat_upper_right",
            ],
        )
    )

    assert added == []

    assert actions(
        hand,
        "FLOP",
    ) == []

    assert (
        hand.players_to_act
        == before
    )

    result = tracker.ingest({
        "episode_id": 4,
        "seat": "hero",
        "street": "FLOP",
        "action": "BET_OR_RAISE",
        "confidence": 0.95,
        "measurements": {
            "stack_change": {
                "delta_bb": 3.0,
            }
        },
        "evidence": [
            "stack_changed",
            "bet_region_occupied",
        ],
        "ts": 2.0,
    })

    assert result is None

    assert actions(
        hand,
        "FLOP",
    ) == []

    assert (
        hand.players_to_act
        == before
    )


if __name__ == "__main__":
    test_quantitative_action_does_not_infer_predecessors()
    test_actor_chronology_then_quantitative_preflop()
    test_actor_chronology_then_quantitative_postflop()
    test_blocker_prevents_passive_skip()

    print(
        "complete action-order regressions passed: "
        "chronology evidence owns skipped-seat inference; "
        "quantitative evidence never fabricates predecessors"
    )
