from src.api.api_boundary_stack_worker import (
    process_request,
)


def test_empty_request():
    result = process_request({
        "type": "boundary_stack_request",
        "request_id": "test-request",
        "hand_token": "test-hand",
        "street": "FLOP",
        "boundary_ts": 123.0,
        "seats": [],
        "frames": [],
    })

    assert result["type"] == "boundary_stack_result"
    assert result["request_id"] == "test-request"
    assert result["hand_token"] == "test-hand"
    assert result["street"] == "FLOP"
    assert result["observations"] == []
    assert result["elapsed_ms"] >= 0.0


def test_missing_frames_are_nonfatal():
    result = process_request({
        "type": "boundary_stack_request",
        "request_id": "missing-frame",
        "hand_token": "test-hand",
        "street": "TURN",
        "boundary_ts": 456.0,
        "seats": ["hero", "seat_mid_left"],
        "frames": [
            {
                "ts": 455.0,
                "frame_path": "/definitely/not/a/frame.png",
                "local_board_count": 3,
            },
        ],
    })

    assert result["street"] == "TURN"
    assert len(result["observations"]) == 2

    for item in result["observations"]:
        assert item["observation"] is None


if __name__ == "__main__":
    test_empty_request()
    test_missing_frames_are_nonfatal()
    print("boundary stack worker contract: PASS")
