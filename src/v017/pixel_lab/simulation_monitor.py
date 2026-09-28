"""
V0.17 controlled simulation visual monitor.

OBSERVATION-ONLY UI.

This module has no poker-semantic authority.

It displays:
    * the exact PNG submitted to production;
    * the actual FrameTransactionResult;
    * the actual FrameHandObserver state;
    * the actual production publication text.

It MUST NOT import:
    * acr_hand_parser
    * acr_truth_timeline
    * acr_pixel_renderer
    * expected actions / truth metadata

The only poker-semantic transaction is the same
process_frame_transaction() used by live ACR.
"""

from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from src.v017.run_live_observer import (
    FrameTransactionState,
    build_observer_from_frame,
    process_frame_transaction,
)

from src.v017.live_product_sink import (
    publish_current_hand_text,
)


ROOT = Path(__file__).resolve().parents[3]

DEFAULT_INPUT = (
    ROOT
    / "runtime/pixel_lab/observer_input/"
      "controlled_hand_2826906889"
)


class SimulationMonitor:
    def __init__(
        self,
        root,
        observer_input=DEFAULT_INPUT,
        interval_seconds=1.0,
    ):
        self.root = root
        self.observer_input = Path(
            observer_input
        )

        self.paths = tuple(
            sorted(
                self.observer_input.glob(
                    "frame_*.png"
                )
            )
        )

        if not self.paths:
            raise RuntimeError(
                f"no observer PNGs: "
                f"{self.observer_input}"
            )

        self.interval_seconds = float(
            interval_seconds
        )

        self.messages = queue.Queue()

        self.running = False
        self.processing = False
        self.index = 0

        self.observer = None
        self.state = None

        self.last_action_count = 0
        self.last_publication_count = 0

        self.photo = None

        self._build_ui()
        self._bootstrap()

        self.root.after(
            50,
            self._poll_messages,
        )

    def _build_ui(self):
        self.root.title(
            "Poker Intelligence — "
            "Controlled Production Observer"
        )

        self.root.geometry(
            "1500x900"
        )

        outer = ttk.Frame(
            self.root,
            padding=8,
        )
        outer.pack(
            fill="both",
            expand=True,
        )

        controls = ttk.Frame(outer)
        controls.pack(
            fill="x",
            pady=(0, 8),
        )

        self.play_button = ttk.Button(
            controls,
            text="Play",
            command=self.play,
        )
        self.play_button.pack(
            side="left",
        )

        self.pause_button = ttk.Button(
            controls,
            text="Pause",
            command=self.pause,
        )
        self.pause_button.pack(
            side="left",
            padx=(6, 0),
        )

        self.next_button = ttk.Button(
            controls,
            text="Next Frame",
            command=self.next_frame,
        )
        self.next_button.pack(
            side="left",
            padx=(18, 0),
        )

        ttk.Label(
            controls,
            text="Seconds / frame:",
        ).pack(
            side="left",
            padx=(24, 6),
        )

        self.speed = tk.DoubleVar(
            value=self.interval_seconds
        )

        speed_box = ttk.Spinbox(
            controls,
            from_=0.1,
            to=10.0,
            increment=0.1,
            textvariable=self.speed,
            width=6,
        )
        speed_box.pack(
            side="left",
        )

        self.frame_label = ttk.Label(
            controls,
            text="Frame - / -",
        )
        self.frame_label.pack(
            side="left",
            padx=(24, 0),
        )

        self.outcome_label = ttk.Label(
            controls,
            text="Outcome: bootstrap",
        )
        self.outcome_label.pack(
            side="right",
        )

        body = ttk.Panedwindow(
            outer,
            orient="horizontal",
        )
        body.pack(
            fill="both",
            expand=True,
        )

        left = ttk.Frame(body)
        right = ttk.Frame(body)

        body.add(
            left,
            weight=3,
        )
        body.add(
            right,
            weight=2,
        )

        ttk.Label(
            left,
            text=(
                "EXACT FRAME SUBMITTED "
                "TO PRODUCTION"
            ),
        ).pack(
            anchor="w",
        )

        self.image_label = ttk.Label(
            left,
            anchor="center",
        )
        self.image_label.pack(
            fill="both",
            expand=True,
            pady=(5, 8),
        )

        state_frame = ttk.LabelFrame(
            left,
            text="Actual Production State",
            padding=6,
        )
        state_frame.pack(
            fill="x",
        )

        self.state_text = tk.Text(
            state_frame,
            height=12,
            wrap="none",
            font=(
                "Menlo",
                11,
            ),
        )
        self.state_text.pack(
            fill="both",
            expand=True,
        )

        notebook = ttk.Notebook(
            right
        )
        notebook.pack(
            fill="both",
            expand=True,
        )

        event_frame = ttk.Frame(
            notebook
        )
        action_frame = ttk.Frame(
            notebook
        )
        hand_frame = ttk.Frame(
            notebook
        )

        notebook.add(
            event_frame,
            text="Physical Events",
        )
        notebook.add(
            action_frame,
            text="Semantic Actions",
        )
        notebook.add(
            hand_frame,
            text="current_hand.txt",
        )

        self.event_text = tk.Text(
            event_frame,
            wrap="word",
            font=(
                "Menlo",
                10,
            ),
        )
        self.event_text.pack(
            fill="both",
            expand=True,
        )

        self.action_text = tk.Text(
            action_frame,
            wrap="word",
            font=(
                "Menlo",
                10,
            ),
        )
        self.action_text.pack(
            fill="both",
            expand=True,
        )

        self.hand_text = tk.Text(
            hand_frame,
            wrap="none",
            font=(
                "Menlo",
                10,
            ),
        )
        self.hand_text.pack(
            fill="both",
            expand=True,
        )

    def _bootstrap(self):
        first_path = self.paths[0]

        first_image = cv2.imread(
            str(first_path)
        )

        if first_image is None:
            raise RuntimeError(
                f"cannot read {first_path}"
            )

        observer = (
            build_observer_from_frame(
                first_image,
                first_path,
                hand_id="pixel-simulation",
            )
        )

        if observer is None:
            raise RuntimeError(
                "physical PNG bootstrap "
                "unresolved"
            )

        self.observer = observer
        self.state = FrameTransactionState()

        self.last_action_count = len(
            self.observer.hand
            .semantic_actions()
        )

        self.last_publication_count = len(
            self.observer.publications
        )

        self._display_image(
            first_image
        )

        self._refresh_state(
            frame_id=1,
            outcome="BOOTSTRAP",
            events=(),
        )

    def _display_image(
        self,
        bgr,
    ):
        rgb = cv2.cvtColor(
            bgr,
            cv2.COLOR_BGR2RGB,
        )

        image = Image.fromarray(
            rgb
        )

        image.thumbnail(
            (900, 590),
            Image.Resampling.LANCZOS,
        )

        self.photo = ImageTk.PhotoImage(
            image=image
        )

        self.image_label.configure(
            image=self.photo
        )

    @staticmethod
    def _replace_text(
        widget,
        value,
    ):
        widget.delete(
            "1.0",
            "end",
        )
        widget.insert(
            "1.0",
            value,
        )

    def _refresh_state(
        self,
        *,
        frame_id,
        outcome,
        events,
    ):
        hand = self.observer.hand

        lines = [
            f"Frame: {frame_id} / "
            f"{len(self.paths)}",
            f"Street: {hand.street}",
            f"Board: {hand.board}",
            f"Next actor: "
            f"{hand.next_actor}",
            "",
            "TRUSTED STACKS",
        ]

        for seat, value in (
            self.observer
            .trusted_stacks
            .items()
        ):
            lines.append(
                f"  {seat:20s} "
                f"{value}"
            )

        self._replace_text(
            self.state_text,
            "\n".join(lines),
        )

        event_lines = []

        for event in events:
            event_lines.append(
                repr(event)
            )

        if not event_lines:
            event_lines.append(
                "(no physical events "
                "this frame)"
            )

        self._replace_text(
            self.event_text,
            "\n\n".join(
                event_lines
            ),
        )

        actions = (
            hand.semantic_actions()
        )

        action_lines = [
            repr(action)
            for action in actions
        ]

        self._replace_text(
            self.action_text,
            "\n".join(
                action_lines
            ),
        )

        publications = (
            self.observer
            .publications
        )

        if publications:
            product = (
                publications[-1]["text"]
            )

            publish_current_hand_text(
                product
            )

            self._replace_text(
                self.hand_text,
                product,
            )

        self.frame_label.configure(
            text=(
                f"Frame {frame_id} / "
                f"{len(self.paths)}"
            )
        )

        self.outcome_label.configure(
            text=f"Outcome: {outcome}"
        )

    def _process_index(
        self,
        index,
    ):
        path = self.paths[index]

        frame_id = int(
            path.stem.split("_")[-1]
        )

        image = cv2.imread(
            str(path)
        )

        if image is None:
            self.messages.put(
                (
                    "error",
                    f"cannot read {path}",
                )
            )
            return

        try:
            transaction = (
                process_frame_transaction(
                    self.observer,
                    image,
                    path,
                    frame_id,
                    self.state,
                )
            )

            self.messages.put(
                (
                    "frame",
                    {
                        "index": index,
                        "frame_id":
                            frame_id,
                        "image": image,
                        "events":
                            transaction.events,
                        "outcome":
                            transaction.outcome,
                    },
                )
            )

        except Exception as exc:
            self.messages.put(
                (
                    "error",
                    repr(exc),
                )
            )

    def next_frame(self):
        if self.processing:
            return

        if self.index >= len(
            self.paths
        ):
            self.pause()
            return

        self.processing = True

        thread = threading.Thread(
            target=self._process_index,
            args=(self.index,),
            daemon=True,
        )
        thread.start()

    def play(self):
        self.running = True
        self.play_button.configure(
            state="disabled"
        )
        self.pause_button.configure(
            state="normal"
        )
        self.next_frame()

    def pause(self):
        self.running = False
        self.play_button.configure(
            state="normal"
        )
        self.pause_button.configure(
            state="normal"
        )

    def _poll_messages(self):
        try:
            while True:
                typ, payload = (
                    self.messages
                    .get_nowait()
                )

                if typ == "error":
                    self.processing = False
                    self.pause()

                    self.outcome_label.configure(
                        text=(
                            "ERROR: "
                            + str(payload)
                        )
                    )
                    continue

                if typ != "frame":
                    continue

                self._display_image(
                    payload["image"]
                )

                self._refresh_state(
                    frame_id=(
                        payload["frame_id"]
                    ),
                    outcome=(
                        payload["outcome"]
                    ),
                    events=(
                        payload["events"]
                    ),
                )

                self.index = (
                    payload["index"] + 1
                )

                self.processing = False

                if (
                    payload["outcome"]
                    != "CONTINUE"
                ):
                    self.pause()
                    continue

                if self.running:
                    try:
                        delay = max(
                            0.1,
                            float(
                                self.speed.get()
                            ),
                        )
                    except Exception:
                        delay = 1.0

                    self.root.after(
                        int(delay * 1000),
                        self.next_frame,
                    )

        except queue.Empty:
            pass

        self.root.after(
            50,
            self._poll_messages,
        )


def main():
    root = tk.Tk()

    SimulationMonitor(
        root,
    )

    root.mainloop()


if __name__ == "__main__":
    main()
