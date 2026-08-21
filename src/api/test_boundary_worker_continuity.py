from unittest.mock import patch

import src.api.api_boundary_stack_worker as worker


def main():
    request = {
        "request_id": "boundary-continuity-test",
        "hand_token": "hand-test",
        "street": "PREFLOP",
        "next_street": "FLOP",
        "boundary_ts": 10.0,
        "seats": ["seat_lower_left"],
        "previous_stacks": {
            "seat_lower_left": 47.57,
        },
        "frames": [
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

    def fake_family(frame_path, seat):
        if str(frame_path) == "0051_full.png":
            return {
                "seat": seat,
                "candidates": [
                    47.57,
                    47.57,
                    4787.0,
                ],
                "ordinary": {},
                "independent": {},
                "frame_path": str(frame_path),
            }

        return None

    with (
        patch.object(
            worker,
            "boundary_stack_candidates",
            side_effect=fake_family,
        ),
        patch.object(
            worker,
            "trusted_read",
            return_value=None,
        ),
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
    assert observation["mode"] == "continuity"
    assert (
        observation[
            "continuity_previous_stack_bb"
        ]
        == 47.57
    )
    assert observation[
        "continuity_candidates"
    ] == [
        47.57,
        47.57,
        4787.0,
    ]
    assert observation[
        "boundary_evidence_scope"
    ] == "old_street"
    assert observation[
        "local_board_count"
    ] == 0

    print(
        "PASS boundary continuity: catastrophic "
        "4787 OCR cannot override canonical 47.57 "
        "terminal-stack continuity"
    )


if __name__ == "__main__":
    main()
