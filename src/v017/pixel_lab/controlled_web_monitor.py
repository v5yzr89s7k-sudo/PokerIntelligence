"""
V0.17 controlled production-observer web monitor.

DISPLAY / ACQUISITION HARNESS ONLY.

The observer receives only rendered PNG pixels.

Forbidden here:
    acr_hand_parser
    acr_truth_timeline
    acr_pixel_renderer
    expected actions
    expected stacks
    truth metadata

Every frame is processed by the exact production
process_frame_transaction() used by live ACR.
"""

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path
import base64
import json
import threading
import time
import webbrowser

import cv2

from src.v017.run_live_observer import (
    FrameTransactionState,
    GEOMETRY,
    build_observer_from_frame,
    process_frame_transaction,
)
from src.events.detectors.card_presence import (
    hero_cards_visible,
)

from src.v017.live_product_sink import (
    publish_current_hand_text,
)


ROOT = Path(__file__).resolve().parents[3]

OBSERVER_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "controlled_hand_2826906889"
)

HOST = "127.0.0.1"
PORT = 8765


HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Poker Intelligence — Production Observer</title>
<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #101418;
    color: #e8edf2;
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
}

header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 16px;
    background: #171d23;
    border-bottom: 1px solid #303942;
}

header strong {
    font-size: 17px;
}

button {
    background: #26313a;
    color: white;
    border: 1px solid #48545f;
    border-radius: 5px;
    padding: 8px 14px;
    cursor: pointer;
}

button:hover {
    background: #34424d;
}

input {
    width: 65px;
    padding: 7px;
    background: #0f1418;
    color: white;
    border: 1px solid #48545f;
    border-radius: 4px;
}

#status {
    margin-left: auto;
    font-family: Menlo, monospace;
    font-size: 13px;
}

main {
    display: grid;
    grid-template-columns:
        minmax(560px, 1.05fr)
        minmax(560px, 0.95fr);
    gap: 10px;
    padding: 10px;
}

.panel {
    min-width: 0;
    background: #171d23;
    border: 1px solid #303942;
    border-radius: 6px;
    overflow: hidden;
}

.panel h2 {
    margin: 0;
    padding: 9px 12px;
    font-size: 13px;
    letter-spacing: 0.04em;
    background: #20272e;
    border-bottom: 1px solid #303942;
}

#frame {
    display: block;
    width: 100%;
    object-fit: contain;
    background: black;
}

#summary {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 24px;
    padding: 10px 12px;
    font-family: Menlo, monospace;
    font-size: 13px;
    border-top: 1px solid #303942;
}

#hand {
    margin: 0;
    padding: 14px;
    white-space: pre;
    overflow: auto;
    font-family: Menlo, monospace;
    font-size: 13px;
    line-height: 1.45;
    height: 760px;
}

@media (max-width: 1050px) {
    main {
        grid-template-columns: 1fr;
    }

    #hand {
        height: 600px;
    }
}
</style>
</head>

<body>

<header>
    <strong>POKER INTELLIGENCE</strong>

    <button id="play">Play</button>
    <button id="pause">Pause</button>
    <button id="next">Next Frame</button>

    <label>
        sec/frame
        <input
            id="speed"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value="1.0"
        >
    </label>

    <span id="status">connecting...</span>
</header>

<main>
    <section class="panel">
        <h2>EXACT FRAME SUBMITTED TO PRODUCTION</h2>

        <img
            id="frame"
            alt="Exact current production input frame"
        >

        <div id="summary"></div>
    </section>

    <section class="panel">
        <h2>ACTUAL runtime/live/current_hand.txt</h2>
        <pre id="hand"></pre>
    </section>
</main>

<script>
let playing = false;
let timer = null;

async function api(path, options={}) {
    const response = await fetch(
        path,
        options
    );

    if (!response.ok) {
        throw new Error(
            await response.text()
        );
    }

    return response.json();
}

function render(data) {
    document.getElementById(
        "status"
    ).textContent =
        `frame ${data.frame_id}/${data.frame_count} · ` +
        `${data.outcome}`;

    if (data.image) {
        document.getElementById(
            "frame"
        ).src =
            "data:image/jpeg;base64," +
            data.image;
    }

    document.getElementById(
        "summary"
    ).innerHTML =
        `<span><b>Street:</b> ${data.street}</span>` +
        `<span><b>Board:</b> ${(data.board || []).join(" ") || "-"}</span>` +
        `<span><b>Next:</b> ${data.next_actor ?? "-"}</span>`;

    document.getElementById(
        "hand"
    ).textContent =
        data.current_hand || "";
}

async function refresh() {
    render(
        await api("/api/state")
    );
}

async function nextFrame() {
    const data = await api(
        "/api/next",
        {
            method: "POST"
        }
    );

    render(data);

    if (
        data.finished
        || data.outcome !== "CONTINUE"
    ) {
        playing = false;
        clearTimeout(timer);
        return;
    }

    if (playing) {
        let seconds = Number(
            document.getElementById(
                "speed"
            ).value
        );

        if (
            !Number.isFinite(seconds)
            || seconds < 0.1
        ) {
            seconds = 1.0;
        }

        timer = setTimeout(
            nextFrame,
            seconds * 1000
        );
    }
}

document.getElementById(
    "next"
).addEventListener(
    "click",
    async () => {
        playing = false;
        clearTimeout(timer);
        await nextFrame();
    }
);

document.getElementById(
    "play"
).addEventListener(
    "click",
    async () => {
        if (playing) {
            return;
        }

        playing = true;
        await nextFrame();
    }
);

document.getElementById(
    "pause"
).addEventListener(
    "click",
    () => {
        playing = false;
        clearTimeout(timer);
    }
);

refresh();
</script>

</body>
</html>
"""


class ControlledSimulation:

    def __init__(
        self,
        observer_input=OBSERVER_INPUT,
    ):
        self.lock = threading.Lock()

        self.paths = tuple(
            sorted(
                Path(observer_input).glob(
                    "frame_*.png"
                )
            )
        )

        if not self.paths:
            raise RuntimeError(
                "no controlled observer PNGs"
            )

        first_path = self.paths[0]

        first_image = cv2.imread(
            str(first_path)
        )

        if first_image is None:
            raise RuntimeError(
                f"cannot read {first_path}"
            )

        # No observer exists until the SAME physical Hero-card
        # acquisition signal used by live becomes visible.
        #
        # The monitor has no knowledge of the ACR hand history,
        # private simulator state, expected cards, or acquisition
        # frame number.
        self.observer = None

        self.transaction_state = (
            FrameTransactionState()
        )

        # Frame 1 is already displayed immediately.
        self.index = 1

        self.frame_id = int(
            first_path.stem.split("_")[-1]
        )

        self.image = first_image
        self.events = ()

        self.outcome = (
            "WAITING_FOR_PHYSICAL_ACQUISITION"
        )

        self.finished = False

    def _publish_latest(self):
        if (
            self.observer is not None
            and self.observer.publications
        ):
            publish_current_hand_text(
                self.observer
                .publications[-1]["text"]
            )

    @staticmethod
    def _encode_image(image):
        ok, encoded = cv2.imencode(
            ".jpg",
            image,
            [
                int(
                    cv2.IMWRITE_JPEG_QUALITY
                ),
                88,
            ],
        )

        if not ok:
            return ""

        return base64.b64encode(
            encoded.tobytes()
        ).decode("ascii")

    def snapshot(self):
        if self.observer is None:
            actions = ()
            street = "WAITING"
            board = []
            next_actor = None
            trusted_stacks = {}
        else:
            actions = tuple(
                self.observer.hand
                .semantic_actions()
            )

            street = (
                self.observer.hand.street
            )

            board = list(
                self.observer.hand.board
            )

            next_actor = (
                self.observer.hand.next_actor
            )

            trusted_stacks = dict(
                self.observer
                .trusted_stacks
            )

        current_hand = ""

        live_path = (
            ROOT
            / "runtime/live/current_hand.txt"
        )

        if live_path.exists():
            current_hand = (
                live_path.read_text(
                    encoding="utf-8"
                )
            )

        return {
            "frame_id":
                self.frame_id,
            "frame_count":
                len(self.paths),
            "street":
                street,
            "board":
                board,
            "next_actor":
                next_actor,
            "trusted_stacks":
                trusted_stacks,
            "events":
                [
                    dict(event)
                    for event in self.events
                ],
            "actions":
                [
                    dict(action)
                    for action in actions
                ],
            "current_hand":
                current_hand,
            "outcome":
                self.outcome,
            "finished":
                self.finished,
            "image":
                self._encode_image(
                    self.image
                ),
        }

    def next_frame(self):
        with self.lock:

            if self.finished:
                return self.snapshot()

            if self.index >= len(
                self.paths
            ):
                self.finished = True
                return self.snapshot()

            path = self.paths[
                self.index
            ]

            frame_id = int(
                path.stem.split("_")[-1]
            )

            image = cv2.imread(
                str(path)
            )

            if image is None:
                raise RuntimeError(
                    f"cannot read {path}"
                )

            # ----------------------------------------------------
            # PRE-ACQUISITION
            #
            # Use only physical pixels and the exact live acquisition
            # sensor. No frame number or private truth is consulted.
            # ----------------------------------------------------

            if self.observer is None:
                visible = hero_cards_visible(
                    image,
                    GEOMETRY,
                )

                self.frame_id = frame_id
                self.image = image
                self.events = ()

                if not visible:
                    self.outcome = (
                        "WAITING_FOR_PHYSICAL_ACQUISITION"
                    )

                    self.index += 1

                    if self.index >= len(
                        self.paths
                    ):
                        self.finished = True

                    return self.snapshot()

                print(
                    "[CONTROLLED_ACQUISITION]",
                    f"frame={frame_id}",
                    "hero_cards_visible=True",
                    flush=True,
                )

                observer = (
                    build_observer_from_frame(
                        image,
                        path,
                        hand_id="pixel-simulation",
                    )
                )

                if observer is None:
                    raise RuntimeError(
                        "physical PNG bootstrap "
                        "unresolved after physical "
                        "Hero-card acquisition"
                    )

                self.observer = observer

                self.outcome = "BOOTSTRAP"

                self._publish_latest()

                self.index += 1

                if self.index >= len(
                    self.paths
                ):
                    self.finished = True

                return self.snapshot()

            # ----------------------------------------------------
            # POST-ACQUISITION
            #
            # Exact production transaction path used by live.
            # ----------------------------------------------------

            transaction = (
                process_frame_transaction(
                    self.observer,
                    image,
                    path,
                    frame_id,
                    self.transaction_state,
                )
            )

            self.frame_id = frame_id
            self.image = image

            self.events = (
                transaction.events
            )

            self.outcome = (
                transaction.outcome
            )

            self._publish_latest()

            self.index += 1

            if (
                transaction.outcome
                != "CONTINUE"
                or self.index
                >= len(self.paths)
            ):
                self.finished = True

            return self.snapshot()


SIMULATION = None


class Handler(
    BaseHTTPRequestHandler
):
    def log_message(
        self,
        format,
        *args,
    ):
        return

    def _send_bytes(
        self,
        data,
        content_type,
        status=200,
    ):
        self.send_response(status)
        self.send_header(
            "Content-Type",
            content_type,
        )
        self.send_header(
            "Cache-Control",
            "no-store",
        )
        self.send_header(
            "Content-Length",
            str(len(data)),
        )
        self.end_headers()
        self.wfile.write(data)

    def _json(
        self,
        payload,
        status=200,
    ):
        data = json.dumps(
            payload,
            default=str,
        ).encode("utf-8")

        self._send_bytes(
            data,
            "application/json; charset=utf-8",
            status,
        )

    def do_GET(self):
        if self.path == "/":
            self._send_bytes(
                HTML.encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if self.path == "/api/state":
            self._json(
                SIMULATION.snapshot()
            )
            return

        self._send_bytes(
            b"not found",
            "text/plain",
            404,
        )

    def do_POST(self):
        if self.path == "/api/next":
            try:
                self._json(
                    SIMULATION.next_frame()
                )
            except Exception as exc:
                self._json(
                    {
                        "error":
                            repr(exc)
                    },
                    500,
                )
            return

        self._send_bytes(
            b"not found",
            "text/plain",
            404,
        )


def main():
    global SIMULATION

    print(
        "===== CONTROLLED WEB MONITOR =====",
        flush=True,
    )

    print(
        "observer input =",
        OBSERVER_INPUT,
        flush=True,
    )

    SIMULATION = ControlledSimulation()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    )

    url = (
        f"http://{HOST}:{PORT}/"
    )

    print(
        "monitor =",
        url,
        flush=True,
    )

    print(
        "Observer input is PNG-only.",
        flush=True,
    )

    print(
        "Production transaction = "
        "process_frame_transaction().",
        flush=True,
    )

    threading.Timer(
        0.5,
        lambda: webbrowser.open(url),
    ).start()

    try:
        server.serve_forever(
            poll_interval=0.25
        )
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()

        print(
            "\nCONTROLLED WEB MONITOR CLOSED",
            flush=True,
        )


if __name__ == "__main__":
    main()
