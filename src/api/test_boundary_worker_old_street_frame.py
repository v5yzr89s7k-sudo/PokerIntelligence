from unittest.mock import patch

import src.api.api_boundary_stack_worker as worker


def main():
    request = {
        "request_id": "boundary-frame-test",
        "hand_token": "hand-test",
        "street": "PREFLOP",
        "next_street": "FLOP",
        "boundary_ts": 10.0,
        "seats": ["utg"],
        "frames": [
            {
                "ts": 8.0,
                "frame_path": "0049_full.png",
                "local_board_count": 0,
            },
            {
                "ts": 9.0,
                "frame_path": "0051_full.png",
                "local_board_count": 0,
            },
            {
                "ts": 10.0,
                "frame_path": "0052_full.png",
                "local_board_count": 3,
            },
        ],
    }

    reads = {
        # Correct old-street terminal stack.
        "0051_full.png": {
            "seat": "utg",
            "stack_bb": 47.57,
            "confidence": 0.98,
            "votes": 4,
            "mode": "independent_segmentation",
            "frame_path": "0051_full.png",
        },

        # Deliberately bad first-FLOP read. This must NOT win.
        "0052_full.png": {
            "seat": "utg",
            "stack_bb": 4787.0,
            "confidence": 0.98,
            "votes": 4,
            "mode": "independent_segmentation",
            "frame_path": "0052_full.png",
        },
    }

    def fake_read(frame_path, seat):
        return reads.get(str(frame_path))

    with patch.object(
        worker,
        "trusted_read",
        side_effect=fake_read,
    ):
        result = worker.process_request(
            request
        )

    observation = (
        result["observations"][0]
        ["observation"]
    )

    assert observation is not None
    assert observation["stack_bb"] == 47.57
    assert (
        observation["frame_path"]
        == "0051_full.png"
    )
    assert observation["local_board_count"] == 0
    assert (
        observation["boundary_evidence_scope"]
        == "old_street"
    )

    print(
        "PASS boundary worker chronology: "
        "PREFLOP terminal evidence comes from "
        "the newest trusted PREFLOP frame, "
        "not the first FLOP frame"
    )


if __name__ == "__main__":
    main()
