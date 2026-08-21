from pathlib import Path
from tempfile import TemporaryDirectory
import json

from src.api import api_event_coordinator as c


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)

        old_requests = c.STACK_REQUESTS
        old_results = c.STACK_RESULTS

        try:
            c.STACK_REQUESTS = (
                root / "stack_requests.jsonl"
            )
            c.STACK_RESULTS = (
                root / "stack_results.jsonl"
            )

            state = c.fresh_state()
            state["hand_token"] = "stack-hand"

            request_id = (
                c.queue_stack_worker_request(
                    state,
                    seat="hero",
                    street="PREFLOP",
                    frame_path="/tmp/frame.png",
                    purpose="settled",
                )
            )

            assert request_id

            request = json.loads(
                c.STACK_REQUESTS
                .read_text()
                .splitlines()[0]
            )

            assert request["type"] == "stack_request"
            assert request["seat"] == "hero"
            assert request["street"] == "PREFLOP"
            assert request["purpose"] == "settled"

            c.append_jsonl(
                c.STACK_RESULTS,
                {
                    "type": "stack_result",
                    "request_id": request_id,
                    "hand_token": "stack-hand",
                    "seat": "hero",
                    "street": "PREFLOP",
                    "frame": "/tmp/frame.png",
                    "purpose": "settled",
                    "ok": True,
                    "reading": {
                        "stack_bb": 98.0,
                        "stack_text": "98 BB",
                        "confidence": 0.95,
                        "votes": 2,
                        "mode": "test",
                        "raw": [],
                    },
                    "independent": {
                        "stack_bb": 98.0,
                        "confidence": 0.98,
                        "votes": 5,
                        "mode": "test_independent",
                        "raw": [],
                    },
                    "elapsed_ms": 500.0,
                },
            )

            ready = (
                c.collect_ready_stack_worker_results(
                    state
                )
            )

            assert set(ready) == {"hero"}

            assert (
                ready["hero"]
                ["result"]
                ["reading"]
                ["stack_bb"]
                == 98.0
            )

            assert (
                state[
                    "pending_stack_worker_requests"
                ]
                == {}
            )

            print(
                "PASS stack worker transport: "
                "settled OCR request/result is "
                "asynchronous and hand-token scoped"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
