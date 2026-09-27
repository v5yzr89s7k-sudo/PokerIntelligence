from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

import src.v017.run_live_observer as live


def main():
    original = live.read_board_identity

    calls = []

    def fake_reader(
        frame_path,
        expected_count,
    ):
        calls.append(
            (
                str(frame_path),
                int(expected_count),
            )
        )

        sleep(0.05)

        return [
            "As",
            "Kd",
            "7c",
        ]

    live.read_board_identity = fake_reader

    reader = live.AsyncBoardIdentityReader()

    try:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "frame.png"
            path.write_bytes(b"immutable")

            boundary = {
                "frame": 100,
                "type":
                    "FLOP_BOUNDARY_PHYSICAL",
                "board_count": 3,
            }

            submitted = reader.submit_if_idle(
                frame_path=path,
                boundary_event=boundary,
                expected_count=3,
            )

            assert submitted is True

            # One outstanding request owns transport.
            assert (
                reader.submit_if_idle(
                    frame_path=path,
                    boundary_event=boundary,
                    expected_count=3,
                )
                is False
            )

            # Submission itself must not wait for reader completion.
            immediate = reader.collect_ready()

            if immediate is not None:
                # A very fast machine is still valid, but ownership
                # metadata must remain exact.
                result = immediate
            else:
                result = None

                for _ in range(100):
                    sleep(0.01)
                    result = reader.collect_ready()

                    if result is not None:
                        break

            assert result is not None
            assert result["error"] is None

            request = result["request"]

            assert (
                request["boundary_event"]
                == boundary
            )

            assert (
                request["expected_count"]
                == 3
            )

            assert (
                Path(request["frame_path"])
                == path
            )

            assert result["board"] == [
                "As",
                "Kd",
                "7c",
            ]

            assert calls == [
                (
                    str(path),
                    3,
                )
            ]

            # Result collection retires transport ownership.
            assert reader.future is None
            assert reader.request is None

            print(
                "ASYNC BOARD IDENTITY READER: PASS"
            )

    finally:
        reader.close()
        live.read_board_identity = original


if __name__ == "__main__":
    main()
