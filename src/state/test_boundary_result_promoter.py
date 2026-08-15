from src.state.canonical_hand import CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)
from src.state.boundary_result_promoter import (
    promote_boundary_observation,
)


def make_case():
    hand = CanonicalHand().start_hand(
        hand_id="boundary-promoter-test",
        players=[
            {
                "seat": "raiser",
                "name": "Raiser",
                "stack_bb": 100.0,
            },
            {
                "seat": "caller",
                "name": "Caller",
                "stack_bb": 50.0,
            },
            {
                "seat": "folder",
                "name": "Folder",
                "stack_bb": 40.0,
            },
        ],
        hero_cards=[],
        hero_position="unknown",
        positions={
            "raiser": "UTG",
            "caller": "BTN",
            "folder": "BB",
        },
        started_ts=1.0,
    )

    # Historical preflop state before asynchronous boundary recovery.
    hand.players["raiser"].committed_by_street["PREFLOP"] = 7.0
    hand.players["caller"].committed_by_street["PREFLOP"] = 2.0
    hand.players["folder"].committed_by_street["PREFLOP"] = 1.0

    tracker = StreetCommitmentTracker()

    tracker.initialize_street_order(
        "PREFLOP",
        ["raiser", "caller", "folder"],
    )

    tracker.open_response_queue(
        "PREFLOP",
        "raiser",
        ["raiser", "caller", "folder"],
    )

    tracker.record_action(
        "PREFLOP",
        "raiser",
        current_price=7.0,
        last_aggressor="raiser",
        betting_open=True,
    )

    # Board has already advanced before worker result arrives.
    hand.set_board(
        ["2c", "7d", "Jh"],
        ts=10.0,
    )

    return hand, tracker


def trusted(stack):
    return {
        "stack_bb": stack,
        "confidence": 0.98,
        "votes": 2,
        "mode": "agreement_verified",
        "frame_path": "/tmp/frame.png",
        "frame_ts": 9.0,
    }


def test_boundary_fold_promotes_and_consumes_response():
    hand, tracker = make_case()

    result = promote_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="folder",
        observation=trusted(40.0),
    )

    assert result.resolved is True
    assert result.action == "FOLD"

    action = hand.actions[-1]

    assert action.street == "PREFLOP"
    assert action.seat == "folder"
    assert action.action == "FOLD"

    assert hand.current_street == "FLOP"

    assert "folder" not in tracker.players_owing_action(
        "PREFLOP"
    )

    assert hand.players["folder"].folded is True
    assert hand.players["folder"].active is False


def test_boundary_call_promotes_exact_missing_amount():
    hand, tracker = make_case()

    # Caller had 2 BB live commitment and now shows 45 BB from a
    # previous confirmed 50 BB stack: 5 additional BB exactly calls 7.
    result = promote_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="caller",
        observation=trusted(45.0),
    )

    assert result.resolved is True
    assert result.action == "CALL"

    action = hand.actions[-1]

    assert action.street == "PREFLOP"
    assert action.action == "CALL"
    assert action.amount_bb == 5.0

    assert (
        hand.players["caller"]
        .committed_by_street["PREFLOP"]
        == 7.0
    )

    assert "caller" not in tracker.players_owing_action(
        "PREFLOP"
    )


def test_untrusted_observation_does_not_mutate():
    hand, tracker = make_case()

    before_actions = len(hand.actions)
    before_owing = tracker.players_owing_action(
        "PREFLOP"
    )

    result = promote_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="folder",
        observation={
            "stack_bb": 40.0,
            "confidence": 0.75,
            "votes": 1,
            "mode": "plain_only",
            "frame_path": "/tmp/frame.png",
            "frame_ts": 9.0,
        },
    )

    assert result.resolved is False
    assert len(hand.actions) == before_actions
    assert tracker.players_owing_action(
        "PREFLOP"
    ) == before_owing


def test_non_owing_player_does_not_mutate():
    hand, tracker = make_case()

    tracker.record_response(
        "PREFLOP",
        "folder",
    )

    before_actions = len(hand.actions)

    result = promote_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="folder",
        observation=trusted(40.0),
    )

    assert result.resolved is False
    assert len(hand.actions) == before_actions

def test_unopened_postflop_unchanged_stack_promotes_check():
    hand, tracker = make_case()

    # Move the same hand to FLOP and initialize the preserved
    # postflop traversal queue.
    hand.set_board(
        ["8d", "8h", "As"],
        ts=10.0,
    )

    tracker.reset_street("FLOP")
    tracker.initialize_street_order(
        "FLOP",
        hand.players_to_act,
    )
    tracker.sync_queue(
        "FLOP",
        hand.players_to_act,
    )

    seat = hand.players_to_act[0]
    player = hand.players[seat]

    # Trusted boundary observation shows no stack decrease.
    observed_stack = player.last_confirmed_stack_bb

    before_owing = tracker.players_owing_action(
        "FLOP"
    )

    assert seat in before_owing, before_owing

    result = promote_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="FLOP",
        seat=seat,
        observation={
            "seat": seat,
            "stack_bb": observed_stack,
            "confidence": 0.98,
            "votes": 4,
            "mode": "independent_segmentation",
            "frame_path": "/tmp/flop_boundary.png",
            "frame_ts": 11.0,
        },
    )

    assert result.resolved is True, result
    assert result.action == "CHECK", result

    checks = [
        action
        for action in hand.actions
        if action.street == "FLOP"
        and action.seat == seat
        and action.action == "CHECK"
    ]

    assert len(checks) == 1, checks

    after_owing = tracker.players_owing_action(
        "FLOP"
    )

    assert seat not in after_owing, after_owing

    print(
        "PASS unopened postflop boundary: "
        "trusted unchanged stack resolves CHECK "
        "and consumes traversal obligation"
    )

if __name__ == "__main__":
    test_boundary_fold_promotes_and_consumes_response()
    test_boundary_call_promotes_exact_missing_amount()
    test_untrusted_observation_does_not_mutate()
    test_non_owing_player_does_not_mutate()
    test_unopened_postflop_unchanged_stack_promotes_check()

    print(
        "PASS boundary result promoter: "
        "trusted old-street FOLD/CALL resolutions promote canonically "
        "and consume preserved response obligations; unsafe evidence "
        "does not mutate state"
    )
