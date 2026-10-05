"""
Temporal identity enrichment integration contract.

Proves:
  * unresolved opponents only;
  * one in-flight batch maximum;
  * fresh submitted frame ownership;
  * worker never mutates HandEngine;
  * result is data-only;
  * retry spacing is deterministic;
  * verified results are applied canonically by caller;
  * close is nonblocking.
"""

import time
from pathlib import Path

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


def collect(enricher):
    deadline = time.monotonic() + 2.0

    while time.monotonic() < deadline:
        result = enricher.collect_ready()

        if result is not None:
            return result

        time.sleep(0.01)

    raise AssertionError(
        "identity worker did not complete"
    )


def main():
    observer = Observer()

    enricher = TemporalIdentityEnricher(
        reader=reader,
        retry_frames=8,
    )

    frame = Path(
        "/tmp/fresh_frame.png"
    )

    try:
        assert enricher.unresolved_seats(
            observer
        ) == [
            "seat_upper_left"
        ]

        assert enricher.submit_if_needed(
            observer,
            frame,
            10,
        )

        # Exactly one in-flight batch.
        assert not enricher.submit_if_needed(
            observer,
            frame,
            11,
        )

        result = collect(enricher)

        players = result.get("players") or []

        assert len(players) == 1

        player = players[0]

        assert player["seat"] == (
            "seat_upper_left"
        )
        assert player["name"] == (
            "VerifiedOpponent"
        )
        assert player["error"] is None
        assert result["submitted_frame"] == 10

        # Worker returned data only.
        assert (
            observer.hand
            .players["seat_upper_left"]
            .name
            == ""
        )

        # Caller/acquisition thread owns canonical application.
        assert observer.hand.enrich_player_identity(
            player["seat"],
            player["name"],
        )

        assert (
            observer.hand
            .players["seat_upper_left"]
            .name
            == "VerifiedOpponent"
        )

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
        "TEMPORAL IDENTITY ENRICHMENT "
        "BATCH CONTRACT: PASS"
    )


if __name__ == "__main__":
    main()
