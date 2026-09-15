import json
import os
import tempfile
from pathlib import Path

import cv2
import numpy as np

import src.api.api_snapshot_worker as worker


def main():
    original_replay = os.environ.get(
        "POKER_REPLAY_SESSION"
    )

    original_run_snapshot = (
        worker.run_snapshot
    )

    original_event_log = (
        worker.EVENT_LOG
    )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            session = root / "session"
            session.mkdir()

            live = root / "api_events.jsonl"

            frame = root / "0042_full.png"

            image = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            assert cv2.imwrite(
                str(frame),
                image,
            )

            recorded_request_id = (
                "recorded-request-42"
            )

            (
                session
                / "snapshot_requests.jsonl"
            ).write_text(
                json.dumps({
                    "type":
                        "snapshot_request",
                    "source_request_id":
                        recorded_request_id,
                    "hand_token":
                        "recorded-hand",
                    "canonical_frame":
                        str(frame),
                    "roster_seats": [
                        "hero",
                        "seat_mid_right",
                    ],
                    "dealt_in_seats": [
                        "hero",
                        "seat_mid_right",
                    ],
                })
                + "\n"
            )

            recorded_snapshot = {
                "players": [
                    {
                        "seat": "hero",
                        "name": "Hero",
                        "stack_text": "20 BB",
                        "stack_bb": 20.0,
                        "is_hero": True,
                        "is_active": True,
                    },
                    {
                        "seat":
                            "seat_mid_right",
                        "name":
                            "RecordedOpponent",
                        "stack_text":
                            "50 BB",
                        "stack_bb":
                            50.0,
                        "is_hero":
                            False,
                        "is_active":
                            True,
                    },
                ],
                "dealer_button_seat":
                    "seat_mid_right",
                "occupied_seats": [
                    "hero",
                    "seat_mid_right",
                ],
                "roster_seats": [
                    "hero",
                    "seat_mid_right",
                ],
                "dealt_in_seats": [
                    "hero",
                    "seat_mid_right",
                ],
                "confidence": 1.0,
            }

            (
                session
                / "snapshot_results.jsonl"
            ).write_text(
                json.dumps({
                    "type":
                        "snapshot_result",
                    "source_request_id":
                        recorded_request_id,
                    "hand_token":
                        "recorded-hand",
                    "canonical_frame":
                        str(frame),
                    "snapshot":
                        recorded_snapshot,
                })
                + "\n"
            )

            os.environ[
                "POKER_REPLAY_SESSION"
            ] = str(session)

            worker.EVENT_LOG = live

            def forbidden_run_snapshot(
                *args,
                **kwargs,
            ):
                raise AssertionError(
                    "LIVE run_snapshot CALLED "
                    "DURING REPLAY"
                )

            worker.run_snapshot = (
                forbidden_run_snapshot
            )

            event = {
                "type":
                    "snapshot_request",
                "ts":
                    42.0,
                "source_request_id":
                    "runtime-request-42",
                "hand_token":
                    "runtime-hand",
                "canonical_frame":
                    str(frame),
                "roster_seats": [
                    "hero",
                    "seat_mid_right",
                ],
                "dealt_in_seats": [
                    "hero",
                    "seat_mid_right",
                ],
            }

            worker.process_event(
                event,
                set(),
            )

            emitted = [
                json.loads(line)
                for line in (
                    live.read_text()
                    .splitlines()
                )
            ]

            snapshots = [
                item
                for item in emitted
                if item.get("type")
                == "table_snapshot"
            ]

            assert len(snapshots) == 1

            names = {
                player.get("seat"):
                    player.get("name")
                for player in (
                    snapshots[0].get(
                        "players"
                    )
                    or []
                )
            }

            assert (
                names[
                    "seat_mid_right"
                ]
                == "RecordedOpponent"
            )

            assert (
                snapshots[0].get(
                    "source_request_id"
                )
                == "runtime-request-42"
            )

            print(
                "PASS: process_event emitted "
                "recorded snapshot"
            )

            print(
                "PASS: replay never called "
                "live run_snapshot"
            )

            missing = root / "9999_full.png"

            assert cv2.imwrite(
                str(missing),
                image,
            )

            missing_event = dict(
                event
            )

            missing_event["ts"] = 43.0

            missing_event[
                "source_request_id"
            ] = "runtime-missing"

            missing_event[
                "canonical_frame"
            ] = str(missing)

            failed_closed = False

            try:
                worker.process_event(
                    missing_event,
                    set(),
                )
            except RuntimeError as exc:
                failed_closed = (
                    "recorded snapshot result "
                    "not found"
                    in str(exc)
                )

            assert failed_closed

            print(
                "PASS: missing recorded "
                "snapshot fails closed"
            )

    finally:
        worker.run_snapshot = (
            original_run_snapshot
        )

        worker.EVENT_LOG = (
            original_event_log
        )

        if original_replay is None:
            os.environ.pop(
                "POKER_REPLAY_SESSION",
                None,
            )
        else:
            os.environ[
                "POKER_REPLAY_SESSION"
            ] = original_replay


if __name__ == "__main__":
    main()
