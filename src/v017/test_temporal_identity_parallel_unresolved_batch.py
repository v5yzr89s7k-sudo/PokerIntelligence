from pathlib import Path
import time

from src.v017.run_live_observer import (
    TemporalIdentityEnricher,
)


class Player:
    def __init__(self, name=""):
        self.name = name


class Hand:
    def __init__(self):
        self.players = {
            "seat_top": Player(""),
            "seat_upper_right": Player(""),
            "seat_mid_right": Player(""),
            "hero": Player("Hero"),
        }


class Observer:
    hero_seat = "hero"

    def __init__(self):
        self.hand = Hand()


CALLS = []


def reader(frame, dealt_in_seats=None):
    seats = tuple(dealt_in_seats or ())
    CALLS.append(seats)

    return {
        "players": [
            {
                "seat": seat,
                "name": f"Name_{seat}",
                "is_hero": False,
            }
            for seat in seats
        ]
    }


def main():
    observer = Observer()

    enricher = TemporalIdentityEnricher(
        reader=reader,
        retry_frames=8,
    )

    frame = Path("/tmp/fresh_identity_batch.png")

    try:
        assert enricher.submit_if_needed(
            observer,
            frame,
            10,
        )

        deadline = time.monotonic() + 2.0
        result = None

        while time.monotonic() < deadline:
            result = enricher.collect_ready()

            if result is not None:
                break

            time.sleep(0.01)

        assert result is not None

        expected = (
            "seat_top",
            "seat_upper_right",
            "seat_mid_right",
        )

        assert CALLS == [expected], (
            "RED: temporal identity recovery still "
            f"submits one seat at a time: {CALLS!r}"
        )

        players = result.get("players") or []

        assert tuple(
            row["seat"]
            for row in players
        ) == expected

        assert all(
            row["name"]
            for row in players
        )

        # Worker remains data-only.
        assert all(
            observer.hand.players[seat].name == ""
            for seat in expected
        )

        print(
            "TEMPORAL IDENTITY FRESH-FRAME BATCH: PASS"
        )
        print(
            "V0.17 PARALLEL UNRESOLVED IDENTITY "
            "RECOVERY: PASS"
        )

    finally:
        enricher.close()


if __name__ == "__main__":
    main()
