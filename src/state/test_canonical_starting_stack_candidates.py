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


def main():
    tests = [
        test_unresolved_candidates_are_not_canonical,
        test_candidates_survive_round_trip,
        test_snapshot_refresh_preserves_candidate_contract,
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
