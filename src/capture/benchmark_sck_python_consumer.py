import socket
import struct
from statistics import mean, median
from time import perf_counter

import numpy as np
import cv2

SOCKET = "/tmp/poker_intelligence_frame.sock"

WIDTH = 934
HEIGHT = 696
CHANNELS = 4

EXPECTED = WIDTH * HEIGHT * CHANNELS


def recv_exact(sock, n):
    data = bytearray()

    while len(data) < n:
        chunk = sock.recv(
            n - len(data)
        )

        if not chunk:
            raise RuntimeError(
                "sampler disconnected"
            )

        data.extend(chunk)

    return bytes(data)


def main():
    s = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    )

    print(
        "[PY] waiting for sampler socket..."
    )

    s.connect(SOCKET)

    print(
        "[PY] connected"
    )

    times = []

    last = None

    for i in range(120):
        header = recv_exact(
            s,
            4,
        )

        size = struct.unpack(
            ">I",
            header,
        )[0]

        if size != EXPECTED:
            raise RuntimeError(
                f"unexpected payload "
                f"{size} != {EXPECTED}"
            )

        payload = recv_exact(
            s,
            size,
        )

        now = perf_counter()

        arr = np.frombuffer(
            payload,
            dtype=np.uint8,
        ).reshape(
            HEIGHT,
            WIDTH,
            CHANNELS,
        )

        # BGRA -> BGR view/copy for OpenCV pipeline.
        bgr = cv2.cvtColor(
            arr,
            cv2.COLOR_BGRA2BGR,
        )

        if last is not None:
            ms = (
                now - last
            ) * 1000.0

            times.append(ms)

            print(
                f"{i:03d} "
                f"python_interval="
                f"{ms:7.2f} ms"
            )

        last = now

    print()
    print(
        "=" * 64
    )
    print(
        "PYTHON CONSUMER RESULT"
    )
    print(
        "=" * 64
    )

    print(
        "samples :",
        len(times),
    )
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
