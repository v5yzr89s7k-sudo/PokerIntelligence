import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand()

    hand.start_hand(
        hand_id="boundary-early-replay",
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "seat_mid_left",
                "name": "Villain",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="UTG+1",
        positions={
            "hero": "UTG+1",
            "seat_mid_left": "HJ",
        },
        started_ts=1.0,
    )

    hand.set_board(
        ["8d", "8h", "As", "Jh"],
        ts=2.0,
    )

    return hand


def main():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None

    hand = make_hand()
    sm.canonical_save(hand)

    state = sm.default_state()
    state["phase"] = "TURN"
    state["hand_token"] = "test-token"
    state["canonical_snapshot_ready"] = True
    state["board"] = ["8d", "8h", "As", "Jh"]

    tracker = sm.tracker_for_hand(hand)

    result = {
        "type": "boundary_stack_result",
        "request_id": "turn-result-1",
        "hand_token": "test-token",
        "street": "TURN",
        "boundary_ts": 3.0,
        "ts": 4.0,
        "observations": [
            {
                "seat": "hero",
                "observation": {
                    "seat": "hero",
                    "stack_bb": (
                        hand.players["hero"]
                        .last_confirmed_stack_bb
                    ),
                    "confidence": 0.98,
                    "votes": 5,
                    "mode": "independent_segmentation",
                    "frame_path": "/tmp/turn.png",
                    "frame_ts": 3.0,
                },
            }
        ],
    }

    state = sm.handle_boundary_stack_result(
        state,
        result,
    )

    assert len(
        state.get("pending_boundary_results") or []
    ) == 1

    assert not any(
        action.street == "TURN"
        and action.seat == "hero"
        and action.action == "CHECK"
        for action in sm.canonical_load().actions
    )

    state = sm.handle_board(
        state,
        {
            "type": "board",
            "board": [
                "8d",
                "8h",
                "As",
                "Jh",
                "9c",
            ],
            "ts": 5.0,
        },
    )

    hand = sm.canonical_load()

    checks = [
        action
        for action in hand.actions
        if action.street == "TURN"
        and action.seat == "hero"
        and action.action == "CHECK"
    ]

    assert len(checks) == 1, checks

    assert not (
        state.get("pending_boundary_results") or []
    )

    print(
        "PASS early boundary result replay: "
        "TURN result buffers while current=TURN and "
        "replays after board advances to RIVER"
    )


if __name__ == "__main__":
    main()
