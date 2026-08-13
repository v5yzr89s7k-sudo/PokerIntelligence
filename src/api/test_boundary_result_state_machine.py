from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.betting_round_tracker import BettingRoundTracker


def build_case():
    canonical = CanonicalHand().start_hand(
        hand_id="boundary-sm-test",
        players=[
            {
                "seat": "raiser",
                "name": "Raiser",
                "stack_bb": 100.0,
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
            "raiser": "BTN",
            "folder": "BB",
        },
        started_ts=1.0,
    )

    canonical.players["raiser"].committed_by_street[
        "PREFLOP"
    ] = 7.0
    canonical.players["folder"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    tracker = BettingRoundTracker(canonical)

    ct = tracker.commitment_tracker

    ct.initialize_street_order(
        "PREFLOP",
        ["raiser", "folder"],
    )

    ct.open_response_queue(
        "PREFLOP",
        "raiser",
        ["raiser", "folder"],
    )

    ct.record_action(
        "PREFLOP",
        "raiser",
        current_price=7.0,
        last_aggressor="raiser",
        betting_open=True,
    )

    canonical.set_board(
        ["2c", "7d", "Jh"],
        ts=10.0,
    )

    state = sm.default_state()
    state["phase"] = "FLOP"
    state["board"] = ["2c", "7d", "Jh"]
    state["hand_token"] = "live-token-A"
    state["canonical_snapshot_ready"] = True

    return canonical, tracker, state


def result(token="live-token-A"):
    return {
        "type": "boundary_stack_result",
        "request_id": "request-1",
        "hand_token": token,
        "street": "PREFLOP",
        "boundary_ts": 9.0,
        "observations": [
            {
                "seat": "folder",
                "observation": {
                    "seat": "folder",
                    "stack_bb": 40.0,
                    "confidence": 0.98,
                    "votes": 2,
                    "mode": "agreement_verified",
                    "frame_path": "/tmp/frame.png",
                    "frame_ts": 9.0,
                    "local_board_count": 3,
                },
            },
        ],
    }


def test_matching_result_promotes():
    canonical, tracker, state = build_case()

    old_store = sm.CANONICAL_STORE
    old_tracker = sm._ACTIVE_TRACKER
    old_hand_id = sm._ACTIVE_HAND_ID
    old_status = sm.BETTING_ROUND_STATUS_PATH

    class FakeStore:
        text_path = Path("/tmp/current_hand.txt")

        def load(self):
            return canonical

        def save(self, hand):
            assert hand is canonical

    with TemporaryDirectory() as td:
        try:
            sm.CANONICAL_STORE = FakeStore()
            sm._ACTIVE_TRACKER = tracker
            sm._ACTIVE_HAND_ID = canonical.hand_id
            sm.BETTING_ROUND_STATUS_PATH = (
                Path(td) / "status.json"
            )

            state = sm.handle_boundary_stack_result(
                state,
                result(),
            )

        finally:
            sm.CANONICAL_STORE = old_store
            sm._ACTIVE_TRACKER = old_tracker
            sm._ACTIVE_HAND_ID = old_hand_id
            sm.BETTING_ROUND_STATUS_PATH = old_status

    matches = [
        action
        for action in canonical.actions
        if action.street == "PREFLOP"
        and action.seat == "folder"
        and action.action == "FOLD"
        and action.source == "boundary_stack_resolution"
    ]

    assert len(matches) == 1
    assert canonical.current_street == "FLOP"

    assert "folder" not in (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
    )


def test_stale_token_does_not_mutate():
    canonical, tracker, state = build_case()

    before = len(canonical.actions)

    old_store = sm.CANONICAL_STORE
    old_tracker = sm._ACTIVE_TRACKER
    old_hand_id = sm._ACTIVE_HAND_ID

    class FakeStore:
        text_path = Path("/tmp/current_hand.txt")

        def load(self):
            return canonical

        def save(self, hand):
            raise AssertionError(
                "stale result must not save canonical"
            )

    try:
        sm.CANONICAL_STORE = FakeStore()
        sm._ACTIVE_TRACKER = tracker
        sm._ACTIVE_HAND_ID = canonical.hand_id

        sm.handle_boundary_stack_result(
            state,
            result(token="stale-token"),
        )

    finally:
        sm.CANONICAL_STORE = old_store
        sm._ACTIVE_TRACKER = old_tracker
        sm._ACTIVE_HAND_ID = old_hand_id

    assert len(canonical.actions) == before
    assert "folder" in (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
    )


if __name__ == "__main__":
    test_matching_result_promotes()
    test_stale_token_does_not_mutate()

    print(
        "PASS boundary result state machine: "
        "matching asynchronous old-street evidence promotes through "
        "the preserved in-memory tracker; stale hand results do nothing"
    )
