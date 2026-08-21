from pathlib import Path
import json
import time


class PacedReplayCapture:
    """
    Present an ActionSequenceRecorder session as a live capture source.

    Frames are released according to their original recorded timestamps.
    Scheduling uses absolute elapsed time from replay start, so time spent
    processing worker results does not accumulate artificial replay delay.

    This module performs no perception and knows nothing about poker.
    """

    def __init__(
        self,
        session,
        *,
        start_frame=1,
        end_frame=None,
    ):
        self.session = Path(session)
        self.start_frame = int(start_frame)
        self.end_frame = (
            int(end_frame)
            if end_frame is not None
            else None
        )

        self.records = self._load_records()

        self.tournament_level = {}

        for record in self.records:
            recorded_level = dict(
                record.get("tournament_level")
                or {}
            )

            if recorded_level:
                self.tournament_level = recorded_level
                break


        if not self.records:
            raise RuntimeError(
                f"no replay frames found in {self.session}"
            )

        self.index = 0
        self.started_monotonic = None
        self.first_recorded_ts = float(
            self.records[0]["ts"]
        )

        # Semantic detector time for the frame most recently released.
        #
        # Wall-clock replay scheduling may catch up by releasing overdue
        # frames immediately. Stateful perception must still observe the
        # original recorded spacing between those frames.
        self.current_recorded_elapsed = 0.0

    def _load_records(self):
        records = []

        for metadata_path in sorted(
            self.session.glob("*_metadata.json")
        ):
            try:
                frame_index = int(
                    metadata_path.name.split("_")[0]
                )
            except (TypeError, ValueError):
                continue

            if frame_index < self.start_frame:
                continue

            if (
                self.end_frame is not None
                and frame_index > self.end_frame
            ):
                continue

            try:
                metadata = json.loads(
                    metadata_path.read_text()
                )
            except Exception:
                continue

            ts = metadata.get("ts")

            if ts is None:
                continue

            frame_path = (
                self.session
                / f"{frame_index:04d}_full.png"
            )

            if not frame_path.exists():
                continue

            records.append({
                "index": frame_index,
                "ts": float(ts),
                "frame_path": frame_path,
                "tournament_level": dict(
                    metadata.get("tournament_level")
                    or {}
                ),
            })

        records.sort(
            key=lambda item: item["index"]
        )

        return records

    def capture(self):
        if self.index >= len(self.records):
            # A real table does not disappear when our selected hand ends.
            # Keep presenting the final post-hand frame so asynchronous
            # workers and the state machine can settle normally.
            time.sleep(0.10)
            return self.records[-1]["frame_path"]

        if self.started_monotonic is None:
            self.started_monotonic = time.monotonic()

        record = self.records[self.index]

        target_elapsed = (
            float(record["ts"])
            - self.first_recorded_ts
        )

        # Publish semantic time before the frame enters perception.
        self.current_recorded_elapsed = target_elapsed

        actual_elapsed = (
            time.monotonic()
            - self.started_monotonic
        )

        remaining = (
            target_elapsed
            - actual_elapsed
        )

        if remaining > 0:
            time.sleep(remaining)

        self.index += 1

        actual_elapsed = (
            time.monotonic()
            - self.started_monotonic
        )

        late_by = max(
            0.0,
            actual_elapsed - target_elapsed,
        )

        print(
            "[REPLAY_CAPTURE] "
            f"frame={record['index']:04d} "
            f"recorded_elapsed={target_elapsed:.3f}s "
            f"actual_elapsed={actual_elapsed:.3f}s "
            f"late_by={late_by:.3f}s",
            flush=True,
        )

        # Durable replay timing history. This is instrumentation only:
        # it does not alter scheduling or perception semantics.
        replay_latency_path = (
            Path(__file__).resolve().parents[2]
            / "runtime/live/replay_latency.jsonl"
        )

        replay_latency_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with replay_latency_path.open("a") as handle:
            handle.write(
                json.dumps({
                    "frame": record["index"],
                    "frame_path": str(
                        record["frame_path"]
                    ),
                    "recorded_ts": record["ts"],
                    "recorded_elapsed": round(
                        target_elapsed,
                        6,
                    ),
                    "actual_elapsed": round(
                        actual_elapsed,
                        6,
                    ),
                    "late_by": round(
                        late_by,
                        6,
                    ),
                    "capture_monotonic": round(
                        time.monotonic(),
                        6,
                    ),
                })
                + "\n"
            )
            handle.flush()

        # Replay-debug synchronization only. Publish the exact frame most
        # recently released so the runner can pair each current_hand.txt
        # change with the table image that was current at that moment.
        frame_state_path = (
            Path(__file__).resolve().parents[2]
            / "runtime/live/current_replay_frame.json"
        )

        frame_state_path.write_text(
            json.dumps(
                {
                    "frame": record["index"],
                    "frame_path": str(
                        record["frame_path"]
                    ),
                    "recorded_elapsed": round(
                        target_elapsed,
                        6,
                    ),
                    "actual_elapsed": round(
                        actual_elapsed,
                        6,
                    ),
                    "recorded_ts": record["ts"],
                },
                indent=2,
            )
            + "\n"
        )

        return record["frame_path"]

    @property
    def exhausted(self):
        return self.index >= len(self.records)

    @property
    def current_index(self):
        if self.index <= 0:
            return None

        return self.records[
            min(self.index - 1, len(self.records) - 1)
        ]["index"]
