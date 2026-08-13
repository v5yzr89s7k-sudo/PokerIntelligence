from pathlib import Path

from src.api.paced_replay_capture import (
    PacedReplayCapture,
)


ROOT = Path(__file__).resolve().parents[2]

SESSION = (
    ROOT
    / "runtime/debug/action_sequence/20260809_124419"
)


def main():
    replay = PacedReplayCapture(
        SESSION,
        start_frame=2,
        end_frame=5,
    )

    assert [
        item["index"]
        for item in replay.records
    ] == [2, 3, 4, 5]

    assert replay.records[0]["frame_path"].name == (
        "0002_full.png"
    )

    assert replay.records[-1]["frame_path"].name == (
        "0005_full.png"
    )

    elapsed = [
        round(
            item["ts"]
            - replay.records[0]["ts"],
            6,
        )
        for item in replay.records
    ]

    assert elapsed[0] == 0.0
    assert elapsed[1] > 0.0
    assert elapsed == sorted(elapsed)

    print("frames:", [
        item["index"]
        for item in replay.records
    ])

    print("elapsed:", elapsed)

    print()
    print(
        "PASS paced replay capture contract: "
        "recorded frames preserve chronological timestamps"
    )


if __name__ == "__main__":
    main()
