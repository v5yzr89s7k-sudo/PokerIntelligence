import socket
import struct
import tempfile
import threading
from pathlib import Path

import numpy as np

from src.capture.sck_frame_source import (
    SCKFrameSource,
    WIDTH,
    HEIGHT,
    CHANNELS,
)


def server(path):
    sock = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )

    sock.bind(path)
    sock.listen(1)

    conn, _ = sock.accept()

    try:
        frame = np.zeros(
            (
                HEIGHT,
                WIDTH,
                CHANNELS,
            ),
            dtype=np.uint8,
        )

        frame[:, :, 0] = 10
        frame[:, :, 1] = 20
        frame[:, :, 2] = 30
        frame[:, :, 3] = 255

        payload = frame.tobytes()

        conn.sendall(
            struct.pack(
                ">I",
                len(payload),
            )
        )

        conn.sendall(payload)

    finally:
        conn.close()
        sock.close()


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = str(
            Path(tmp) / "frame.sock"
        )

        thread = threading.Thread(
            target=server,
            args=(path,),
            daemon=True,
        )

        thread.start()

        import time

        deadline = time.time() + 2.0

        while (
            not Path(path).exists()
            and time.time() < deadline
        ):
            time.sleep(0.01)

        source = SCKFrameSource(
            socket_path=path
        )

        try:
            frame = source.read()
        finally:
            source.close()

        assert frame.shape == (
            HEIGHT,
            WIDTH,
            3,
        )

        # BGRA -> BGR
        assert tuple(
            int(v)
            for v in frame[0, 0]
        ) == (
            10,
            20,
            30,
        )

        print(
            "PASS SCK frame source contract: "
            "raw BGRA socket payload becomes canonical "
            "934x696 OpenCV BGR frame"
        )


if __name__ == "__main__":
    main()
