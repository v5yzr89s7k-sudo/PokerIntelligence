from pathlib import Path
import tempfile

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "seat_lower_left"


def main():
    old_results = c.STACK_RESULTS
    old_canonical = c.CANONICAL_HAND_JSON

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        results_path = root / "stack_results.jsonl"
        canonical_path = root / "canonical_hand.json"

        c.STACK_RESULTS = results_path
        c.CANONICAL_HAND_JSON = canonical_path

        try:
            canonical_path.write_text(
                """
{
  "players": {
    "seat_lower_left": {
      "starting_stack_bb": 48.57,
      "current_stack_bb": 48.57,
      "last_confirmed_stack_bb": 48.57
    }
  }
}
""".strip()
                + "\n"
            )

            state = c.fresh_state()
            state["hand_token"] = "hand-1"
            state["phase"] = "PREFLOP"

            # Transport owns request-old.
            state[
                "pending_stack_worker_requests"
            ] = {
                "request-old": {
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "frame": "/tmp/0052_full.png",
                    "purpose": "settled",
                    "hand_token": "hand-1",
                    "queued_ts": 1.0,
                }
            }

            # Semantic candidate has moved on to another request.
            #
            # This is precisely the dangerous state: transport has a completed
            # result, but the candidate cannot acknowledge that result.
            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": 1.0,
                    "last_change_ts": 1.0,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    "stack_worker_request_id": (
                        "request-new"
                    ),
                    "last_stack_sample_ts": 1.0,
                    "ocr_attempts": 1,
                    "hand_token": "hand-1",
                }
            }

            results_path.write_text(
                """
{"type":"stack_result","request_id":"request-old","hand_token":"hand-1","seat":"seat_lower_left","street":"PREFLOP","frame":"/tmp/0052_full.png","purpose":"settled","ok":true,"reading":{"raw":[{"variant":"green","raw":"47.57 BB","stack_bb":47.57},{"variant":"plain","raw":"47.57 BB","stack_bb":47.57},{"variant":"psm13_t130","raw":"4787 BB","stack_bb":4787.0}],"stack_bb":47.57,"stack_text":"47.57 BB","confidence":0.5,"votes":1,"mode":"segmentation_disagreement"},"independent":{"stack_bb":4787.0,"stack_text":"4787 BB","confidence":0.98,"votes":4,"mode":"independent_segmentation","raw":[]},"error":null,"elapsed_ms":582.1,"ts":2.0}
""".strip()
                + "\n"
            )

            ready = (
                c.collect_ready_stack_worker_results(
                    state
                )
            )

            print(
                "transport after collect:",
                state[
                    "pending_stack_worker_requests"
                ],
            )
            print(
                "ready:",
                {
                    seat: item.get("request_id")
                    for seat, item in ready.items()
                },
            )

            # Simulate the normal semantic handoff.
            changes = ChangeSet()

            # Candidate is intentionally too young to perform any unrelated
            # retry work. The ownership mismatch itself is what matters.
            c.process_stack_change_measurements_async(
                changes,
                None,
                state,
                stack_worker_results=ready,
                prior_occupied_bet_regions=set(),
                prior_commitment_seats=set(),
                event_street="PREFLOP",
                frame_path="/tmp/0052_full.png",
                frame_ts=1.1,
            )

            semantic_request = (
                state[
                    "pending_stack_reads"
                ][SEAT].get(
                    "stack_worker_request_id"
                )
            )

            transport_still_owns_old = (
                "request-old"
                in state[
                    "pending_stack_worker_requests"
                ]
            )

            print(
                "semantic request:",
                semantic_request,
            )
            print(
                "transport still owns old:",
                transport_still_owns_old,
            )

            # REQUIRED INVARIANT:
            #
            # A completed result that semantic candidate ownership cannot
            # acknowledge may not disappear from all durable ownership.
            assert transport_still_owns_old, (
                "REPRODUCED: collector retired completed "
                "settled-stack transport before semantic "
                "candidate acknowledged the result"
            )

            print(
                "PASS settled stack result ownership: "
                "unacknowledged result remains durably owned"
            )


            # ------------------------------------------------------------
            # Missing semantic request ownership
            # ------------------------------------------------------------
            #
            # Transport still owns a completed settled-stack request, but
            # the semantic candidate currently owns NO request id.
            #
            # Exact ownership requires request_id equality. Absence of a
            # semantic request id is not permission to retire transport.
            state = c.fresh_state()
            state["hand_token"] = "hand-1"
            state["phase"] = "PREFLOP"

            state[
                "pending_stack_worker_requests"
            ] = {
                "request-orphan": {
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "frame": "/tmp/0054_full.png",
                    "purpose": "settled",
                    "hand_token": "hand-1",
                    "queued_ts": 3.0,
                }
            }

            state["pending_stack_reads"] = {
                SEAT: {
                    "first_change_ts": 3.0,
                    "last_change_ts": 3.0,
                    "origin_street": "PREFLOP",
                    "trigger_sources": [
                        "stack_motion",
                    ],
                    # Intentionally NO stack_worker_request_id.
                    "last_stack_sample_ts": 3.0,
                    "ocr_attempts": 1,
                    "hand_token": "hand-1",
                }
            }

            results_path.write_text(
                """
{"type":"stack_result","request_id":"request-orphan","hand_token":"hand-1","seat":"seat_lower_left","street":"PREFLOP","frame":"/tmp/0054_full.png","purpose":"settled","ok":true,"reading":{"raw":[{"variant":"green","raw":"47.57 BB","stack_bb":47.57},{"variant":"plain","raw":"47.57 BB","stack_bb":47.57}],"stack_bb":47.57,"stack_text":"47.57 BB","confidence":0.98,"votes":2,"mode":"agreement_verified"},"independent":{"stack_bb":47.57,"stack_text":"47.57 BB","confidence":0.98,"votes":4,"mode":"independent_segmentation","raw":[]},"error":null,"elapsed_ms":582.1,"ts":4.0}
""".strip()
                + "\n"
            )

            ready = (
                c.collect_ready_stack_worker_results(
                    state
                )
            )

            transport_still_owns_orphan = (
                "request-orphan"
                in state[
                    "pending_stack_worker_requests"
                ]
            )

            print()
            print(
                "missing-owner ready:",
                {
                    seat: item.get("request_id")
                    for seat, item in ready.items()
                },
            )
            print(
                "missing-owner transport retained:",
                transport_still_owns_orphan,
            )

            assert ready == {}, (
                "RED: collector exposed completed settled-stack "
                "result even though semantic candidate owns no "
                "request id"
            )

            assert transport_still_owns_orphan, (
                "RED: collector retired settled-stack transport "
                "without exact semantic request ownership"
            )

            print(
                "PASS missing semantic request ownership: "
                "transport remains durable"
            )

        finally:
            c.STACK_RESULTS = old_results
            c.CANONICAL_HAND_JSON = old_canonical


if __name__ == "__main__":
    main()
