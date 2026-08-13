from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


SEAT = "seat_mid_right"


def make_hand():
    return CanonicalHand().start_hand(
        hand_id="baseline-observation-test",
        players=[
            {
                "seat": SEAT,
                "name": "Villain",
                "stack_bb": None,
                "stack_candidates": [
                    99.41,
                    55.41,
                ],
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


def test_unique_observation_promotes_baseline():
    original_store = sm.CANONICAL_STORE

    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=root / "canonical_hand.json",
                text_path=root / "current_hand.txt",
            )

            sm.CANONICAL_STORE.save(make_hand())

            state = sm.default_state()
            state["phase"] = "PREFLOP"
            state["canonical_snapshot_ready"] = True

            state = sm.handle_stack_baseline_observation(
                state,
                {
                    "type": "stack_baseline_observation",
                    "seat": SEAT,
                    "observed_stack_bb": 55.41,
                    "confidence": 0.98,
                    "votes": 5,
                    "mode": "independent_segmentation",
                    "ts": 2.0,
                },
            )

            hand = sm.CANONICAL_STORE.load()
            player = hand.players[SEAT]

            assert player.starting_stack_bb == 55.41
            assert player.current_stack_bb == 55.41
            assert player.last_confirmed_stack_bb == 55.41

            # Now the ordinary stack-update path must derive the real delta
            # from canonical absolute endpoints.
            state = sm.handle_stack_update(
                state,
                {
                    "type": "stack_update",
                    "seat": SEAT,
                    "previous_stack_bb": 55.41,
                    "current_stack_bb": 53.41,
                    "delta_bb": 2.0,
                    "confidence": 0.95,
                    "ts": 3.0,
                },
            )

            hand = sm.CANONICAL_STORE.load()
            player = hand.players[SEAT]

            assert player.starting_stack_bb == 55.41
            assert player.current_stack_bb == 53.41
            assert player.last_confirmed_stack_bb == 53.41

    finally:
        sm.CANONICAL_STORE = original_store


def test_unmatched_observation_does_not_promote():
    hand = make_hand()

    result = hand.resolve_starting_stack_baseline(
        SEAT,
        53.41,
    )

    assert result["resolved"] is False
    assert (
        result["reason"]
        == "no_matching_starting_candidate"
    )

    player = hand.players[SEAT]

    assert player.starting_stack_bb is None
    assert player.current_stack_bb is None
    assert player.last_confirmed_stack_bb is None


def test_existing_canonical_stack_cannot_be_overwritten():
    hand = make_hand()

    first = hand.resolve_starting_stack_baseline(
        SEAT,
        55.41,
    )

    assert first["resolved"] is True

    second = hand.resolve_starting_stack_baseline(
        SEAT,
        99.41,
    )

    assert second["resolved"] is False
    assert (
        second["reason"]
        == "canonical_stack_already_initialized"
    )

    player = hand.players[SEAT]

    assert player.starting_stack_bb == 55.41
    assert player.current_stack_bb == 55.41
    assert player.last_confirmed_stack_bb == 55.41


def main():
    tests = [
        test_unique_observation_promotes_baseline,
        test_unmatched_observation_does_not_promote,
        test_existing_canonical_stack_cannot_be_overwritten,
    ]

    for test in tests:
        test()
        print("PASS", test.__name__)

    print()
    print(
        "PASS stack baseline observation state machine: "
        "trusted pre-change absolute evidence can uniquely "
        "initialize unresolved canonical stack state without "
        "action semantics or inferred delta"
    )


if __name__ == "__main__":
    main()
