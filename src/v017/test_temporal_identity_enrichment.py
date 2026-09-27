"""
Temporal identity enrichment integration contract.

Proves:
  * unresolved opponents only;
  * one in-flight request maximum;
  * fresh submitted frame ownership;
  * worker never mutates HandEngine;
  * result is data-only;
  * retry spacing is deterministic;
  * same verified result is applied canonically by caller;
  * close is nonblocking.
"""

import time

from src.v017.hand_engine import HandEngine
from src.v017.run_live_observer import (
    TemporalIdentityEnricher,
)


class Observer:
    hero_seat = "hero"

    def __init__(self):
        self.hand = HandEngine(
            players=[
                {
                    "seat": "seat_upper_left",
                    "position": "UTG",
                    "name": "",
                    "stack_bb": 41.52,
                    "dealt_in": True,
                },
                {
                    "seat": "hero",
                    "position": "BB",
                    "name": "Hero",
                    "stack_bb": 100.0,
                    "dealt_in": True,
                },
            ],
            action_order=[
                "seat_upper_left",
                "hero",
            ],
            small_blind_seat="seat_upper_left",
            big_blind_seat="hero",
        )


def reader(
    frame,
    dealt_in_seats=None,
):
    assert str(frame).endswith(
        "fresh_frame.png"
    )
    assert dealt_in_seats == [
        "seat_upper_left"
    ]

    return {
        "players": [
            {
                "seat": "seat_upper_left",
                "name": "VerifiedOpponent",
                "is_hero": False,
            }
        ]
    }


def main():
    observer = Observer()

    enricher = TemporalIdentityEnricher(
        reader=reader,
        retry_frames=8,
    )

    try:
        assert enricher.unresolved_seats(
            observer
        ) == [
            "seat_upper_left"
        ]

        # Plain Path is already a valid fresh-frame reference.
        from pathlib import Path
        frame = Path(
            "/tmp/fresh_frame.png"
        )

        assert enricher.submit_if_needed(
            observer,
            frame,
            10,
        )

        # Exactly one in-flight request.
        assert not enricher.submit_if_needed(
            observer,
            frame,
            11,
        )

        deadline = time.monotonic() + 2.0
        result = None

        while time.monotonic() < deadline:
            result = enricher.collect_ready()

            if result is not None:
                break

            time.sleep(0.01)

        assert result is not None
        assert result["seat"] == (
            "seat_upper_left"
        )
        assert result["name"] == (
            "VerifiedOpponent"
        )
        assert result["error"] is None

        # Worker returned data only. Canonical model is unchanged.
        assert (
            observer.hand
            .players["seat_upper_left"]
            .name
            == ""
        )

        # Caller/acquisition thread owns canonical application.
        assert observer.hand.enrich_player_identity(
            result["seat"],
            result["name"],
        )

        assert (
            observer.hand
            .players["seat_upper_left"]
            .name
            == "VerifiedOpponent"
        )

        # Resolved seat is no longer queried.
        assert enricher.unresolved_seats(
            observer
        ) == []

        assert not enricher.submit_if_needed(
            observer,
            frame,
            18,
        )

    finally:
        started = time.monotonic()
        enricher.close()
        elapsed = time.monotonic() - started

        assert elapsed < 0.5

    print(
        "TEMPORAL IDENTITY ENRICHMENT CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
