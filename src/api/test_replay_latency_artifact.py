from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from src.api.paced_replay_capture import (
    PacedReplayCapture,
)


def main():
    with TemporaryDirectory() as tmp:
        session = Path(tmp)

        for index, ts in (
            (1, 100.0),
            (2, 100.5),
        ):
            (
                session
                / f"{index:04d}_metadata.json"
            ).write_text(
                json.dumps({
                    "ts": ts,
                })
            )

            (
                session
                / f"{index:04d}_full.png"
            ).write_bytes(b"x")

        replay = PacedReplayCapture(session)

        # Redirect runtime artifact root through patched __file__ parent
        # behavior by temporarily using the real runtime file, then clean it.
        root = Path(__file__).resolve().parents[2]
        artifact = (
            root
            / "runtime/live/replay_latency.jsonl"
        )

        old = (
            artifact.read_text()
            if artifact.exists()
            else None
        )

        try:
            artifact.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            artifact.write_text("")

            with patch(
                "src.api.paced_replay_capture.time.sleep",
                return_value=None,
            ):
                replay.capture()

            rows = [
                json.loads(line)
                for line in artifact
                .read_text()
                .splitlines()
                if line.strip()
            ]

            assert len(rows) == 1

            row = rows[0]

            assert row["frame"] == 1
            assert "recorded_elapsed" in row
            assert "actual_elapsed" in row
            assert "late_by" in row

            assert row["late_by"] >= 0.0

            print(
                "PASS replay latency artifact: "
                "every released frame records durable "
                "recorded/actual/late timing"
            )

        finally:
            if old is None:
                if artifact.exists():
                    artifact.unlink()
            else:
                artifact.write_text(old)


if __name__ == "__main__":
    main()
