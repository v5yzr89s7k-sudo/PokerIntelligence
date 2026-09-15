from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import json
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
                "transport-before-baseline"
            )
            state["phase"] = "PREFLOP"

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            # Real physical commitment begins at t=100.0.
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

            candidate = state[
                "pending_stack_reads"
            ][SEAT]

            print(
                "after opening:",
                candidate,
            )

            # Candidate is now beyond the 450ms sampling floor,
            # but canonical baseline is intentionally still absent.
            settled = ChangeSet()

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
                    settled,
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
                    frame_ts=100.60,
                    queue_stack_ocr=True,
                    replay_records=[],
                )

            requests = []

            if c.STACK_REQUESTS.exists():
                for raw in (
                    c.STACK_REQUESTS
                    .read_text()
                    .splitlines()
                ):
                    if not raw.strip():
                        continue

                    requests.append(
                        json.loads(raw)
                    )

            hero = [
                item
                for item in requests
                if (
                    item.get("seat") == SEAT
                    and item.get("purpose")
                    == "settled"
                )
            ]

            print()
            print(
                "settled_requests:",
                hero,
            )

            print(
                "candidate_after:",
                state[
                    "pending_stack_reads"
                ].get(SEAT),
            )

            assert hero, (
                "RED: missing canonical baseline prevented "
                "capture of the time-sensitive settled stack "
                "sample"
            )

            assert len(hero) == 1, (
                "expected exactly one settled transport, got "
                + repr(hero)
            )

            # Interpretation may still be pending. This test
            # requires only that acquisition is no longer
            # blocked by baseline readiness.
            assert (
                state["pending_stack_reads"]
                .get(SEAT)
                is not None
            ), (
                "candidate was destroyed while quantitative "
                "interpretation was still waiting for baseline"
            )

            print()
            print(
                "PASS: settled stack acquisition occurs on "
                "physical time; missing baseline delays "
                "interpretation, not transport"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
