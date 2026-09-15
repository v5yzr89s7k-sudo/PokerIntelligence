from src.state.canonical_hand import CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)

try:
    from src.state.boundary_result_promoter import (
        resolve_boundary_observation,
    )
except ImportError:
    resolve_boundary_observation = None


def make_case():
    hand = CanonicalHand().start_hand(
        hand_id="boundary-resolution-adapter",
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

    hand.players["raiser"].committed_by_street[
        "PREFLOP"
    ] = 7.0

    hand.players["caller"].committed_by_street[
        "PREFLOP"
    ] = 2.0

    hand.players["folder"].committed_by_street[
        "PREFLOP"
    ] = 1.0

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

    return hand, tracker


def trusted(stack):
    return {
        "stack_bb": stack,
        "confidence": 0.98,
        "votes": 4,
        "mode": "agreement_verified",
        "frame_path": "/tmp/frame.png",
        "frame_ts": 9.0,
    }


def test_fold_resolution_is_mutation_free():
    assert resolve_boundary_observation is not None, (
        "RED: mutation-free boundary observation "
        "resolver adapter does not exist"
    )

    hand, tracker = make_case()

    before_actions = list(hand.actions)
    before_status = tracker.round_status(
        "PREFLOP"
    )

    result = resolve_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="folder",
        observation=trusted(40.0),
    )

    after_status = tracker.round_status(
        "PREFLOP"
    )

    print()
    print("===== FOLD RESOLUTION =====")
    print("result:", result)
    print("before:", before_status)
    print("after :", after_status)

    assert result.resolved is True
    assert result.action == "FOLD"

    assert hand.actions == before_actions, (
        "resolver adapter mutated CanonicalHand"
    )

    assert after_status == before_status, (
        "resolver adapter mutated commitment tracker"
    )

    print(
        "PASS: FOLD resolves without mutation"
    )


def test_call_resolution_is_mutation_free():
    assert resolve_boundary_observation is not None

    hand, tracker = make_case()

    before_actions = list(hand.actions)
    before_status = tracker.round_status(
        "PREFLOP"
    )

    result = resolve_boundary_observation(
        hand=hand,
        commitment_tracker=tracker,
        street="PREFLOP",
        seat="caller",
        observation=trusted(45.0),
    )

    after_status = tracker.round_status(
        "PREFLOP"
    )

    print()
    print("===== CALL RESOLUTION =====")
    print("result:", result)

    assert result.resolved is True
    assert result.action == "CALL"
    assert result.amount_bb == 5.0

    assert hand.actions == before_actions
    assert after_status == before_status

    print(
        "PASS: CALL resolves exact amount "
        "without mutation"
    )


def test_untrusted_evidence_remains_unresolved():
    assert resolve_boundary_observation is not None

    hand, tracker = make_case()

    before_actions = list(hand.actions)
    before_status = tracker.round_status(
        "PREFLOP"
    )

    result = resolve_boundary_observation(
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
    assert hand.actions == before_actions
    assert (
        tracker.round_status("PREFLOP")
        == before_status
    )

    print(
        "PASS: unsafe evidence remains "
        "unresolved and mutation-free"
    )


def main():
    test_fold_resolution_is_mutation_free()
    test_call_resolution_is_mutation_free()
    test_untrusted_evidence_remains_unresolved()

    print()
    print(
        "PASS boundary observation resolver "
        "adapter contract"
    )


if __name__ == "__main__":
    main()
