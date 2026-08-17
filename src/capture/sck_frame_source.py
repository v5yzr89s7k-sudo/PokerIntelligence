import socket
import struct
from pathlib import Path

import cv2
import numpy as np


SOCKET_PATH = "/tmp/poker_intelligence_frame.sock"

WIDTH = 934
HEIGHT = 696
CHANNELS = 4
PAYLOAD_SIZE = WIDTH * HEIGHT * CHANNELS


def _recv_exact(sock, size):
    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(
            size - len(data)
        )

        if not chunk:
            raise RuntimeError(
                "ScreenCaptureKit sampler disconnected"
            )

        data.extend(chunk)

    return bytes(data)


class SCKFrameSource:
    """
    Persistent in-memory ScreenCaptureKit frame source.

    Returns canonical 934x696 OpenCV BGR frames.
    No screenshot subprocess.
    No PNG write/read round trip.
    """

    def __init__(
        self,
        socket_path=SOCKET_PATH,
    ):
        self.socket_path = socket_path
        self.sock = None

    def connect(self):
        if self.sock is not None:
            return

        sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )

        sock.connect(
            self.socket_path
        )

        self.sock = sock

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def read(self):
        if self.sock is None:
            self.connect()

        header = _recv_exact(
            self.sock,
            4,
        )

        size = struct.unpack(
            ">I",
            header,
        )[0]

        if size != PAYLOAD_SIZE:
            raise RuntimeError(
                f"unexpected SCK payload size "
                f"{size}; expected {PAYLOAD_SIZE}"
            )

        payload = _recv_exact(
            self.sock,
            size,
        )

        bgra = np.frombuffer(
            payload,
            dtype=np.uint8,
        ).reshape(
            HEIGHT,
            WIDTH,
            CHANNELS,
        )

        return cv2.cvtColor(
            bgra,
            cv2.COLOR_BGRA2BGR,
        )


def main():
    from statistics import mean, median
    from time import perf_counter

    source = SCKFrameSource()

    times = []

    previous = None

    try:
        for i in range(120):
            started = perf_counter()

            frame = source.read()

            elapsed = (
                perf_counter()
                - started
            ) * 1000.0

            times.append(elapsed)

            assert frame.shape == (
                HEIGHT,
                WIDTH,
                3,
            )

            previous = frame

            print(
                f"{i:03d} "
                f"read={elapsed:7.2f}ms"
            )

    finally:
        source.close()

    print()
    print("=" * 64)
    print("SCK FRAME SOURCE")
    print("=" * 64)
    print("samples :", len(times))
    print(
        f"min     : {min(times):.2f} ms"
    )
    print(
        f"median  : {median(times):.2f} ms"
    )
    print(
        f"mean    : {mean(times):.2f} ms"
    )
    print(
        f"max     : {max(times):.2f} ms"
    )


if __name__ == "__main__":
    main()
