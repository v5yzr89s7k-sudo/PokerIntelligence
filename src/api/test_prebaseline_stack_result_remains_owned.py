from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "hero"


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
            state["hand_token"] = (
                "prebaseline-result-owner"
            )
            state["phase"] = "PREFLOP"

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            # -------------------------------------------------
            # 1. Physical commitment opens candidate.
            # -------------------------------------------------

            opening = ChangeSet()
            opening.bet_region_appeared = [SEAT]

            with (
                patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={},
                ),
                patch.object(
                    c,
                    "_canonical_player_ineligible_for_settled_stack",
                    return_value=False,
                ),
            ):
                c.enrich_stack_change_measurements(
                    opening,
                    img,
                    state,
                    prior_occupied_bet_regions=set(),
                    prior_commitment_seats=set(),
                    event_street="PREFLOP",
                    frame_path="/tmp/0100_full.png",
                    frame_ts=100.0,
                    queue_stack_ocr=True,
                    replay_records=[],
                )

            # -------------------------------------------------
            # 2. Sampling epoch matures while baseline absent.
            #    Production must queue the settled sample.
            # -------------------------------------------------

            with (
                patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={},
                ),
                patch.object(
                    c,
                    "_canonical_player_ineligible_for_settled_stack",
                    return_value=False,
                ),
            ):
                c.enrich_stack_change_measurements(
                    ChangeSet(),
                    img,
                    state,
                    prior_occupied_bet_regions={
                        SEAT,
                    },
                    prior_commitment_seats={
                        SEAT,
                    },
                    event_street="PREFLOP",
                    frame_path="/tmp/0101_full.png",
                    frame_ts=100.6,
                    queue_stack_ocr=True,
                    replay_records=[],
                )

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            request_id = entry.get(
                "stack_worker_request_id"
            )

            print(
                "queued_request:",
                request_id,
            )

            assert request_id, (
                "setup failure: prebaseline settled "
                "request was not queued"
            )

            # -------------------------------------------------
            # 3. Worker completes BEFORE canonical baseline.
            #
            # This immutable result is the valuable action-time
            # sample that must not disappear.
            # -------------------------------------------------

            worker_results = {
                SEAT: {
                    "request_id": request_id,
                    "seat": SEAT,
                    "street": "PREFLOP",
                    "frame": "/tmp/0101_full.png",
                    "purpose": "settled",
                    "result": {
                        "ok": True,
                        "reading": {
                            "stack_bb": 53.44,
                            "confidence": 0.98,
                        },
                        "independent": {
                            "stack_bb": 53.44,
                            "confidence": 0.98,
                        },
                    },
                }
            }

            with (
                patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={},
                ),
                patch.object(
                    c,
                    "_canonical_player_ineligible_for_settled_stack",
                    return_value=False,
                ),
            ):
                c.enrich_stack_change_measurements(
                    ChangeSet(),
                    img,
                    state,
                    stack_worker_results=worker_results,
                    prior_occupied_bet_regions={
                        SEAT,
                    },
                    prior_commitment_seats={
                        SEAT,
                    },
                    event_street="PREFLOP",
                    frame_path="/tmp/0102_full.png",
                    frame_ts=100.8,
                    queue_stack_ocr=True,
                    replay_records=[],
                )

            entry = state[
                "pending_stack_reads"
            ].get(SEAT)

            print()
            print(
                "after_worker_before_baseline:",
                entry,
            )

            print(
                "worker_results_after:",
                worker_results,
            )

            assert entry is not None, (
                "RED: candidate disappeared while "
                "baseline was still unavailable"
            )

            # The completed result must remain owned somewhere:
            # either still in transport or explicitly attached
            # to the semantic candidate.
            transport_still_owns = (
                SEAT in worker_results
            )

            candidate_owns = bool(
                entry.get(
                    "prebaseline_worker_item"
                )
                or entry.get(
                    "baseline_pending_worker_item"
                )
            )

            print(
                "transport_still_owns:",
                transport_still_owns,
            )

            print(
                "candidate_owns:",
                candidate_owns,
            )

            assert (
                transport_still_owns
                or candidate_owns
            ), (
                "RED: completed settled stack result "
                "was consumed/discarded before canonical "
                "baseline became available"
            )

            print()
            print(
                "PASS: completed prebaseline settled "
                "result remains durably owned until "
                "quantitative interpretation is possible"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
