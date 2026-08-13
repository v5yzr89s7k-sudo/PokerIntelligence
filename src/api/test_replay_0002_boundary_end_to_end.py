from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.api.api_boundary_stack_worker import (
    process_request,
)
from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.test_replay_0002_preflop_semantics import (
    make_hand,
    inferred,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260808_114630"
)

TOKEN = "replay-0002-e2e"


def build_real_preflop_state():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    # Real observed chronology already validated independently.
    tracker.ingest(
        inferred(
            1,
            "seat_mid_right",
            "BET_OR_RAISE",
            delta_bb=2.0,
            ts=1.0,
        )
    )

    tracker.ingest(
        inferred(
            2,
            "seat_lower_right",
            "CALL_OR_RAISE",
            delta_bb=7.0,
            ts=2.0,
        )
    )

    tracker.ingest(
        inferred(
            3,
            "hero",
            "CALL_OR_RAISE",
            delta_bb=7.0,
            ts=3.0,
        )
    )

    # The normal stack-settlement pipeline has already established these
    # authoritative post-action stacks before the flop boundary.
    confirmed = {
        "seat_mid_right": 53.41,
        "seat_lower_right": 65.08,
        "hero": 25.42,
        "seat_lower_left": 64.13,
        "seat_mid_left": 19.82,
        "seat_upper_left": 37.94,
        "seat_top": 28.36,
    }

    for seat, value in confirmed.items():
        hand.players[seat].last_confirmed_stack_bb = value

    expected_owing = {
        "seat_mid_right",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
        "seat_top",
    }

    actual_owing = (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
    )

    # The response queue owns cyclic action order. This integration test
    # cares that exactly the five real unresolved responders survive to the
    # boundary; it must not impose a second ordering contract on that queue.
    assert set(actual_owing) == expected_owing, (
        actual_owing
    )
    assert len(actual_owing) == len(expected_owing), (
        actual_owing
    )

    return hand, tracker


def make_real_request():
    frames = []

    for idx in range(68, 80):
        path = SESSION / f"{idx:04d}_full.png"

        if not path.exists():
            raise AssertionError(
                f"Replay 0002 frame missing: {path}"
            )

        frames.append({
            "ts": float(idx),
            "frame_path": str(path),
            "local_board_count": (
                3 if idx >= 79 else 0
            ),
        })

    return {
        "type": "boundary_stack_request",
        "request_id": "replay-0002-e2e-request",
        "hand_token": TOKEN,
        "street": "PREFLOP",
        "next_street": "FLOP",
        "boundary_ts": 79.0,
        "seats": [
            "seat_mid_right",
            "seat_lower_left",
            "seat_mid_left",
            "seat_upper_left",
            "seat_top",
        ],
        "frames": frames,
    }


def main():
    hand, tracker = build_real_preflop_state()

    forced = {
        "POST_ANTE",
        "POST_SMALL_BLIND",
        "POST_BIG_BLIND",
    }

    before = [
        (
            action.position,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.action not in forced
    ]

    assert before == [
        ("UTG", "FOLD", None, None),
        ("UTG+1", "RAISE", None, 2.0),
        ("LJ", "RAISE", None, 7.0),
        ("HJ", "CALL", 7.0, None),
    ], before

    request = make_real_request()

    # This is the actual asynchronous perception worker contract.
    result = process_request(request)

    print()
    print("===== REAL WORKER RESULT =====")

    for item in result["observations"]:
        print(item)

    # Board confirmation reaches the state machine before the asynchronous
    # retrospective worker result.
    hand.set_board(
        ["8s", "Qd", "Td"],
        ts=80.0,
    )

    assert hand.current_street == "FLOP"

    state = sm.default_state()
    state["phase"] = "FLOP"
    state["board"] = ["8s", "Qd", "Td"]
    state["hand_token"] = TOKEN
    state["canonical_snapshot_ready"] = True

    old_store = sm.CANONICAL_STORE
    old_tracker = sm._ACTIVE_TRACKER
    old_hand_id = sm._ACTIVE_HAND_ID
    old_status = sm.BETTING_ROUND_STATUS_PATH

    class FakeStore:
        text_path = Path("/tmp/replay-0002-current-hand.txt")

        def load(self):
            return hand

        def save(self, saved):
            assert saved is hand

    with TemporaryDirectory() as td:
        try:
            sm.CANONICAL_STORE = FakeStore()
            sm._ACTIVE_TRACKER = tracker
            sm._ACTIVE_HAND_ID = hand.hand_id
            sm.BETTING_ROUND_STATUS_PATH = (
                Path(td) / "betting_round_status.json"
            )

            state = sm.handle_boundary_stack_result(
                state,
                result,
            )

        finally:
            sm.CANONICAL_STORE = old_store
            sm._ACTIVE_TRACKER = old_tracker
            sm._ACTIVE_HAND_ID = old_hand_id
            sm.BETTING_ROUND_STATUS_PATH = old_status

    actual = [
        (
            action.position,
            action.action,
            action.amount_bb,
            action.raise_to_bb,
        )
        for action in hand.actions
        if action.street == "PREFLOP"
        and action.action not in forced
    ]

    expected = [
        ("UTG", "FOLD", None, None),
        ("UTG+1", "RAISE", None, 2.0),
        ("LJ", "RAISE", None, 7.0),
        ("HJ", "CALL", 7.0, None),
        ("CO", "FOLD", None, None),
        ("BTN", "FOLD", None, None),
        ("SB", "FOLD", None, None),
        ("BB", "FOLD", None, None),
        ("UTG+1", "FOLD", None, None),
    ]

    print()
    print("===== COMPLETE RECOVERED PREFLOP =====")

    for item in actual:
        print(item)

    assert actual == expected, (
        "\nACTUAL:\n"
        + "\n".join(map(str, actual))
        + "\n\nEXPECTED:\n"
        + "\n".join(map(str, expected))
    )

    assert (
        tracker.commitment_tracker
        .players_owing_action("PREFLOP")
        == []
    )

    assert hand.current_street == "FLOP"

    false_flop = [
        action
        for action in hand.actions
        if action.street == "FLOP"
        and action.source == "boundary_stack_resolution"
    ]

    assert false_flop == []

    by_seat = {
        item["seat"]: item["observation"]
        for item in result["observations"]
    }

    # Preserve the real temporal worker proof in the full pipeline.
    # All five terminal stacks are now independently trusted on the exact
    # boundary frame.
    assert by_seat["seat_top"]["stack_bb"] == 28.36

    for seat in (
        "seat_mid_right",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
        "seat_top",
    ):
        assert by_seat[seat]["frame_path"].endswith(
            "0079_full.png"
        )

    print()
    print(
        "PASS Replay 0002 boundary end-to-end: "
        "real frames -> asynchronous trusted stack recovery -> "
        "preserved old-street obligations -> five canonical PREFLOP "
        "folds; known actions preserved; hand remains on FLOP"
    )


if __name__ == "__main__":
    main()
