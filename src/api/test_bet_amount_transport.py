from pathlib import Path
import json
import tempfile

import src.api.api_event_coordinator as coord


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_requests = coord.BET_AMOUNT_REQUESTS
        old_results = coord.BET_AMOUNT_RESULTS
        old_event_log = coord.EVENT_LOG

        try:
            coord.BET_AMOUNT_REQUESTS = (
                root / "bet_amount_requests.jsonl"
            )
            coord.BET_AMOUNT_RESULTS = (
                root / "bet_amount_results.jsonl"
            )
            coord.EVENT_LOG = (
                root / "api_events.jsonl"
            )

            coord.BET_AMOUNT_REQUESTS.write_text("")
            coord.BET_AMOUNT_RESULTS.write_text("")
            coord.EVENT_LOG.write_text("")

            state = coord.fresh_state()
            state["hand_token"] = "hand-test"
            state["phase"] = "PREFLOP"

            frame = root / "frame.png"
            frame.write_bytes(b"test")

            state = coord.queue_bet_amount_request(
                state,
                frame,
                "seat_lower_right",
                "PREFLOP",
            )

            state = coord.queue_bet_amount_request(
                state,
                frame,
                "hero",
                "PREFLOP",
            )

            pending = dict(
                state.get(
                    "pending_bet_amount_requests"
                )
                or {}
            )

            assert len(pending) == 2

            request_lines = [
                json.loads(line)
                for line in (
                    coord.BET_AMOUNT_REQUESTS
                    .read_text()
                    .splitlines()
                )
                if line.strip()
            ]

            assert len(request_lines) == 2

            first = request_lines[0]
            second = request_lines[1]

            assert first["seat"] == "seat_lower_right"
            assert first["street"] == "PREFLOP"
            assert first["hand_token"] == "hand-test"

            assert second["seat"] == "hero"
            assert second["street"] == "PREFLOP"
            assert second["hand_token"] == "hand-test"

            # Complete second request first to prove results do not
            # depend on queue order.
            result_two = {
                "type": "bet_amount_result",
                "request_id": second["request_id"],
                "hand_token": "hand-test",
                "seat": "hero",
                "street": "PREFLOP",
                "frame": str(frame),
                "ok": True,
                "bet_bb": 2.0,
                "elapsed_ms": 100.0,
                "ts": 2.0,
            }

            state, emitted = (
                coord.apply_bet_amount_result(
                    state,
                    result_two,
                )
            )

            assert emitted is True

            pending = dict(
                state.get(
                    "pending_bet_amount_requests"
                )
                or {}
            )

            assert len(pending) == 1
            assert first["request_id"] in pending

            event_lines = [
                json.loads(line)
                for line in (
                    coord.EVENT_LOG
                    .read_text()
                    .splitlines()
                )
                if line.strip()
            ]

            assert [
                event.get("type")
                for event in event_lines
            ] == [
                "provisional_bet_opened",
            ]

            assert (
                event_lines[0]["seat"]
                == "hero"
            )

            assert (
                event_lines[0]["source_request_id"]
                == second["request_id"]
            )

            assert not any(
                event.get("type")
                == "bet_amount_observation"
                for event in event_lines
            )

            deferred = dict(
                state.get(
                    "deferred_bet_amount_results"
                )
                or {}
            )

            assert (
                second["request_id"]
                in deferred
            )

            assert (
                deferred[
                    second["request_id"]
                ]["bet_bb"]
                == 2.0
            )

            # Now complete first request.
            result_one = {
                "type": "bet_amount_result",
                "request_id": first["request_id"],
                "hand_token": "hand-test",
                "seat": "seat_lower_right",
                "street": "PREFLOP",
                "frame": str(frame),
                "ok": True,
                "bet_bb": 2.0,
                "elapsed_ms": 120.0,
                "ts": 3.0,
            }

            state, emitted = (
                coord.apply_bet_amount_result(
                    state,
                    result_one,
                )
            )

            assert emitted is True

            assert not (
                state.get(
                    "pending_bet_amount_requests"
                )
                or {}
            )

            event_lines = [
                json.loads(line)
                for line in (
                    coord.EVENT_LOG
                    .read_text()
                    .splitlines()
                )
                if line.strip()
            ]

            assert [
                event.get("type")
                for event in event_lines
            ] == [
                "provisional_bet_opened",
                "provisional_bet_opened",
            ]

            assert [
                event.get("seat")
                for event in event_lines
            ] == [
                "hero",
                "seat_lower_right",
            ]

            assert {
                event.get(
                    "source_request_id"
                )
                for event in event_lines
            } == {
                first["request_id"],
                second["request_id"],
            }

            assert not any(
                event.get("type")
                == "bet_amount_observation"
                for event in event_lines
            )

            deferred = dict(
                state.get(
                    "deferred_bet_amount_results"
                )
                or {}
            )

            assert set(deferred) == {
                first["request_id"],
                second["request_id"],
            }

            assert (
                deferred[
                    first["request_id"]
                ]["bet_bb"]
                == 2.0
            )

            assert (
                deferred[
                    second["request_id"]
                ]["bet_bb"]
                == 2.0
            )

            # A stale hand result must be consumed from pending
            # transport but may not emit evidence into the new hand.
            event_lines_before_stale = [
                line
                for line in (
                    coord.EVENT_LOG
                    .read_text()
                    .splitlines()
                )
                if line.strip()
            ]

            state = coord.queue_bet_amount_request(
                state,
                frame,
                "seat_lower_left",
                "PREFLOP",
            )

            stale_id = next(iter(
                state[
                    "pending_bet_amount_requests"
                ]
            ))

            stale = {
                "type": "bet_amount_result",
                "request_id": stale_id,
                "hand_token": "old-hand",
                "seat": "seat_lower_left",
                "street": "PREFLOP",
                "frame": str(frame),
                "ok": True,
                "bet_bb": 1.0,
                "elapsed_ms": 90.0,
                "ts": 4.0,
            }

            state, emitted = (
                coord.apply_bet_amount_result(
                    state,
                    stale,
                )
            )

            assert emitted is False
            assert not (
                state.get(
                    "pending_bet_amount_requests"
                )
                or {}
            )

            event_lines_after = [
                line
                for line in (
                    coord.EVENT_LOG
                    .read_text()
                    .splitlines()
                )
                if line.strip()
            ]

            assert (
                event_lines_after
                == event_lines_before_stale
            )

            parsed_events = [
                json.loads(line)
                for line in event_lines_after
            ]

            assert not any(
                event.get("type")
                == "bet_amount_observation"
                for event in parsed_events
            )

            assert [
                event.get("type")
                for event in parsed_events
            ] == [
                "provisional_bet_opened",
                "provisional_bet_opened",
            ]

            print(
                "PASS bet amount transport: "
                "multiple concurrent seat requests, "
                "out-of-order completion, provisional lifecycle "
                "without premature quantitative publication, "
                "deferred transition evidence, "
                "and stale-hand rejection"
            )

        finally:
            coord.BET_AMOUNT_REQUESTS = old_requests
            coord.BET_AMOUNT_RESULTS = old_results
            coord.EVENT_LOG = old_event_log


if __name__ == "__main__":
    main()
