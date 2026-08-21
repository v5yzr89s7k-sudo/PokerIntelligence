from pathlib import Path
from tempfile import TemporaryDirectory
import json

from src.api.paced_replay_capture import PacedReplayCapture


def write_frame(session, index, ts, **extra):
    metadata = {
        "index": index,
        "ts": ts,
        **extra,
    }

    (
        session / f"{index:04d}_metadata.json"
    ).write_text(
        json.dumps(metadata)
    )

    (
        session / f"{index:04d}_full.png"
    ).write_bytes(b"x")


def main():
    expected = {
        "small_blind_chips": 700,
        "big_blind_chips": 1400,
        "ante_chips": 175,
        "small_blind_bb": 0.5,
        "big_blind_bb": 1.0,
        "ante_bb": 0.125,
        "source": "window_title",
        "window_title": (
            "Tournament - 700 / 1,400, "
            "Ante 175 Hold'em"
        ),
    }

    with TemporaryDirectory() as tmp:
        session = Path(tmp)

        write_frame(
            session,
            1,
            100.0,
            tournament_level=expected,
        )
        write_frame(
            session,
            2,
            100.5,
            tournament_level=expected,
        )

        replay = PacedReplayCapture(session)

        assert replay.tournament_level == expected, (
            "replay must expose the tournament level "
            "recorded with the session"
        )

        assert (
            replay.records[0]["tournament_level"]
            == expected
        ), (
            "loaded replay records must preserve "
            "recorded tournament level metadata"
        )

    print(
        "PASS replay tournament level contract: "
        "recorded level survives replay loading"
    )


if __name__ == "__main__":
    main()
