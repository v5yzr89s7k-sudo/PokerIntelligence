from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import json
import numpy as np

from src.api import api_event_coordinator as c
from src.events.local_event_detector import ChangeSet


SEAT = "hero"
BASELINE = 53.44


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
            state["hand_token"] = "continuous-commitment"
            state["phase"] = "PREFLOP"

            img = np.zeros(
                (696, 934, 3),
                dtype=np.uint8,
            )

            # First authoritative physical commitment edge.
            first = ChangeSet()
            first.bet_region_appeared = [SEAT]

            with patch.object(
                c,
                "_canonical_stack_values",
                return_value={
                    SEAT: BASELINE,
                },
            ):
                c.enrich_stack_change_measurements(
                    first,
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

            entry = state[
                "pending_stack_reads"
            ][SEAT]

            print(
                "after opening:",
                entry,
            )

            # Model continuing physical activity from the SAME
            # commitment episode. Each pulse arrives before the
            # 450ms quiet interval.
            #
            # This evidence may keep the candidate alive, but it
            # must not move the first quantitative-sampling floor
            # forever.
            pulse_times = [
                100.20,
                100.40,
                100.60,
                100.80,
                101.00,
            ]

            for number, ts in enumerate(
                pulse_times,
                1,
            ):
                changes = ChangeSet()

                # Continuing stack-region motion associated with
                # the already-open physical commitment.
                changes.stack_changed_seats = [SEAT]

                with (
                    patch.object(
                        c,
                        "_canonical_stack_values",
                        return_value={
                            SEAT: BASELINE,
                        },
                    ),
                    patch.object(
                        c,
                        "_canonical_player_ineligible_for_settled_stack",
                        return_value=False,
                    ),
                ):
                    c.enrich_stack_change_measurements(
                        changes,
                        img,
                        state,
                        prior_occupied_bet_regions={
                            SEAT,
                        },
                        prior_commitment_seats={
                            SEAT,
                        },
                        event_street="PREFLOP",
                        frame_path=(
                            f"/tmp/{100 + number:04d}"
                            "_full.png"
                        ),
                        frame_ts=ts,
                        queue_stack_ocr=True,
                        replay_records=[],
                    )

                current = state[
                    "pending_stack_reads"
                ].get(SEAT)

                print(
                    f"after pulse {number} "
                    f"ts={ts}:",
                    current,
                )

            # Give the candidate a frame well beyond the original
            # 450ms sampling floor, while still less than 450ms
            # from the most recent continuing pulse.
            final = ChangeSet()

            # This regression owns only candidate timing. Canonical
            # player eligibility is a separate transport guard tested
            # elsewhere. Keep Hero explicitly eligible so reaching the
            # worker queue proves the sampling clock is no longer
            # starved by continuing same-episode motion.
            with (
                patch.object(
                    c,
                    "_canonical_stack_values",
                    return_value={
                        SEAT: BASELINE,
                    },
                ),
                patch.object(
                    c,
                    "_canonical_player_ineligible_for_settled_stack",
                    return_value=False,
                ),
            ):
                c.enrich_stack_change_measurements(
                    final,
                    img,
                    state,
                    prior_occupied_bet_regions={
                        SEAT,
                    },
                    prior_commitment_seats={
                        SEAT,
                    },
                    event_street="PREFLOP",
                    frame_path="/tmp/0110_full.png",
                    frame_ts=101.20,
                    queue_stack_ocr=True,
                    replay_records=[],
                )

            requests = []

            if c.STACK_REQUESTS.exists():
                requests = [
                    json.loads(line)
                    for line
                    in c.STACK_REQUESTS
                    .read_text()
                    .splitlines()
                    if line.strip()
                ]

            hero_requests = [
                request
                for request in requests
                if (
                    request.get("seat")
                    == SEAT
                    and request.get("purpose")
                    == "settled"
                )
            ]

            print()
            print(
                "settled_hero_requests:",
                hero_requests,
            )

            assert hero_requests, (
                "RED: continuing physical evidence from one "
                "real commitment repeatedly refreshed "
                "last_change_ts and starved the candidate of "
                "its first settled quantitative stack sample"
            )

            first_request = hero_requests[0]

            print(
                "first_request_frame:",
                first_request.get("frame"),
            )

            print(
                "PASS: continuous same-episode commitment "
                "evidence cannot indefinitely postpone the "
                "first quantitative stack sample"
            )

        finally:
            c.STACK_REQUESTS = old_requests
            c.STACK_RESULTS = old_results


if __name__ == "__main__":
    main()
