from pathlib import Path

from src.api.api_boundary_stack_worker import (
    process_request,
)


SESSION = Path(
    "runtime/debug/action_sequence/20260808_114630"
)


def main():
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

    request = {
        "type": "boundary_stack_request",
        "request_id": "replay-0002-boundary",
        "hand_token": "replay-0002",
        "street": "PREFLOP",
        "boundary_ts": 79.0,
        "seats": [
            "seat_mid_right",   # UTG+1
            "seat_lower_left",  # CO
            "seat_mid_left",    # BTN
            "seat_upper_left",  # SB
            "seat_top",         # BB
        ],
        "frames": frames,
    }

    result = process_request(request)

    print()
    print("===== REPLAY 0002 WORKER RESULT =====")

    for item in result["observations"]:
        print(item)

    assert result["type"] == "boundary_stack_result"
    assert result["street"] == "PREFLOP"
    assert result["hand_token"] == "replay-0002"

    by_seat = {
        item["seat"]: item["observation"]
        for item in result["observations"]
    }

    expected = {
        "seat_mid_right": 53.41,
        "seat_lower_left": 64.13,
        "seat_mid_left": 19.82,
        "seat_upper_left": 37.94,
        "seat_top": 28.36,
    }

    for seat, value in expected.items():
        observation = by_seat.get(seat)

        assert observation is not None, (
            seat,
            result,
        )

        assert observation["stack_bb"] == value, (
            seat,
            observation,
        )

        assert observation["confidence"] >= 0.95, (
            seat,
            observation,
        )

        assert observation["votes"] >= 2, (
            seat,
            observation,
        )

    # Critical Replay 0002 temporal proof:
    #
    # After ACR stack-display precision normalization, the exact boundary
    # frame 79 independently resolves BB to the displayed 28.36 BB with
    # strong consensus. The worker therefore correctly uses the newest
    # trusted boundary frame directly.
    bb = by_seat["seat_top"]

    assert bb["stack_bb"] == 28.36, bb
    assert bb["confidence"] >= 0.95, bb
    assert bb["votes"] >= 3, bb
    assert bb["frame_path"].endswith(
        "0079_full.png"
    ), bb
    assert bb["frame_ts"] == 79.0, bb

    # All five responders now have trusted terminal evidence on frame 79.
    for seat in (
        "seat_mid_right",
        "seat_lower_left",
        "seat_mid_left",
        "seat_upper_left",
        "seat_top",
    ):
        assert by_seat[seat]["frame_path"].endswith(
            "0079_full.png"
        ), (
            seat,
            by_seat[seat],
        )

    # Worker remains perception-only. It must not assign poker semantics.
    text = repr(result).lower()

    assert "'action':" not in text
    assert "fold" not in text
    assert "call" not in text
    assert "check" not in text

    print()
    print(
        "PASS Replay 0002 boundary stack worker: "
        "retrospective OCR automatically recovers trusted terminal "
        "evidence for all five unresolved responders directly from "
        "the boundary frame without poker semantics"
    )


if __name__ == "__main__":
    main()
