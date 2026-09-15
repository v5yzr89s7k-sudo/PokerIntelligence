from src.state.canonical_hand import CanonicalHand


SEAT = "seat_mid_right"


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="candidate-contract",
        players=[
            {
                "seat": SEAT,
                "name": "player",
                "stack_bb": None,
                "stack_candidates": [
                    99.41,
                    55.41,
                ],
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="HJ",
        positions={
            SEAT: "UTG+1",
        },
        started_ts=1.0,
    )


def test_unresolved_candidates_are_not_canonical():
    hand = make_hand()
    player = hand.players[SEAT]

    assert player.starting_stack_bb is None
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None

    assert player.starting_stack_candidates == [
        99.41,
        55.41,
    ]


def test_candidates_survive_round_trip():
    hand = make_hand()

    restored = CanonicalHand.from_dict(
        hand.to_dict()
    )

    player = restored.players[SEAT]

    assert player.starting_stack_bb is None
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None

    assert player.starting_stack_candidates == [
        99.41,
        55.41,
    ]


def test_snapshot_refresh_preserves_candidate_contract():
    hand = make_hand()

    hand.update_table_snapshot(
        players=[
            {
                "seat": SEAT,
                "name": "player",
                "stack_bb": None,
                "stack_candidates": [
                    99.41,
                    55.41,
                ],
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_position="HJ",
        positions={
            SEAT: "UTG+1",
        },
        dealt_in_seats=[SEAT],
    )

    player = hand.players[SEAT]

    assert player.starting_stack_bb is None
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None
    assert player.starting_stack_candidates == [
        99.41,
        55.41,
    ]


def test_later_post_action_observation_cannot_redefine_starting_baseline():
    hand = CanonicalHand().start_hand(
        hand_id="late-baseline-conflict",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": None,
                "stack_candidates": [55.44],
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={"hero": "BTN"},
        started_ts=1.0,
    )

    player = hand.players["hero"]

    assert player.starting_stack_bb is None
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None
    assert player.starting_stack_candidates == [55.44]

    result = hand.resolve_starting_stack_baseline(
        seat="hero",
        observed_stack_bb=53.44,
    )

    assert result is not None
    assert result["resolved"] is False
    assert result["reason"] == "no_matching_starting_candidate"

    player = hand.players["hero"]

    assert player.starting_stack_bb is None, (
        "BUG: later post-action stack 53.44 redefined "
        "historical starting baseline"
    )
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None
    assert player.starting_stack_candidates == [55.44]


def test_matching_pre_action_candidate_can_still_resolve_starting_baseline():
    hand = CanonicalHand().start_hand(
        hand_id="matching-baseline-control",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": None,
                "stack_candidates": [55.44],
                "is_hero": True,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="BTN",
        positions={"hero": "BTN"},
        started_ts=1.0,
    )

    result = hand.resolve_starting_stack_baseline(
        seat="hero",
        observed_stack_bb=55.44,
    )

    assert result is not None
    assert result["resolved"] is True
    assert result["reason"] == "unique_prechange_candidate_match"

    player = hand.players["hero"]

    assert player.starting_stack_bb == 55.44
    assert player.current_stack_bb == 55.44
    assert player.last_confirmed_stack_bb == 55.44


def main():
    tests = [
        test_unresolved_candidates_are_not_canonical,
        test_candidates_survive_round_trip,
        test_snapshot_refresh_preserves_candidate_contract,
        test_later_post_action_observation_cannot_redefine_starting_baseline,
        test_matching_pre_action_candidate_can_still_resolve_starting_baseline,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print()
    print(
        "PASS canonical starting-stack evidence: "
        "unresolved snapshot candidates survive persistence "
        "without becoming canonical stack values"
    )


if __name__ == "__main__":
    main()
