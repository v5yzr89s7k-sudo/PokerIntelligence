import json
import tempfile
from pathlib import Path

import src.api.api_event_coordinator as c


def main():
    old_canonical = c.CANONICAL_HAND_JSON
    old_requests = c.STACK_REQUESTS

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        c.CANONICAL_HAND_JSON = root / "canonical_hand.json"
        c.STACK_REQUESTS = root / "stack_requests.jsonl"

        try:
            state = c.fresh_state()
            state["hand_token"] = "guard-test"
            state["phase"] = "RIVER"

            c.CANONICAL_HAND_JSON.write_text(json.dumps({
                "players": {
                    "seat_upper_right": {
                        "seat": "seat_upper_right",
                        "folded": True,
                        "active": False,
                    },
                    "hero": {
                        "seat": "hero",
                        "folded": False,
                        "active": True,
                    },
                }
            }))

            folded = c.queue_stack_worker_request(
                state,
                seat="seat_upper_right",
                street="RIVER",
                frame_path="/tmp/folded.png",
                purpose="settled",
            )
            assert folded is None
            assert not state["pending_stack_worker_requests"]

            active = c.queue_stack_worker_request(
                state,
                seat="hero",
                street="RIVER",
                frame_path="/tmp/active.png",
                purpose="settled",
            )
            assert active is not None

            baseline = c.queue_stack_worker_request(
                state,
                seat="seat_upper_right",
                street="PREFLOP",
                frame_path="/tmp/baseline.png",
                purpose="baseline",
            )
            assert baseline is not None

            # Fail-open: unavailable canonical state must not suppress
            # legitimate settled transport.
            c.CANONICAL_HAND_JSON.unlink()

            unknown = c.queue_stack_worker_request(
                state,
                seat="seat_mid_left",
                street="RIVER",
                frame_path="/tmp/unknown.png",
                purpose="settled",
            )
            assert unknown is not None

            print(
                "PASS: folded/inactive canonical players cannot queue "
                "new settled-stack OCR; baseline and unknown state remain open"
            )

        finally:
            c.CANONICAL_HAND_JSON = old_canonical
            c.STACK_REQUESTS = old_requests


if __name__ == "__main__":
    main()
