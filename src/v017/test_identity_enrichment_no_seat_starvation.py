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
            "seat_mid_right": Player(""),
            "seat_lower_right": Player(""),
        }


class Observer:
    hero_seat = "hero"

    def __init__(self):
        self.hand = Hand()


CALLS = []


def reader(frame, dealt_in_seats):
    seats = tuple(dealt_in_seats)
    CALLS.append(seats)

    # Deliberately resolve nobody.
    return {
        "players": [
            {
                "seat": seat,
                "name": "",
            }
            for seat in seats
        ]
    }


def collect(enricher):
    for _ in range(100):
        result = enricher.collect_ready()

        if result is not None:
            return result

        time.sleep(0.001)

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
        "/tmp/identity_fairness.png"
    )

    expected = (
        "seat_top",
        "seat_mid_right",
        "seat_lower_right",
    )

    try:
        # All unresolved seats receive the same fresh-frame
        # opportunity. No early unresolved seat can starve another.
        assert enricher.submit_if_needed(
            observer,
            frame,
            1,
        )

        result = collect(enricher)

        assert CALLS == [expected]

        players = result.get("players") or []

        assert tuple(
            row["seat"]
            for row in players
        ) == expected

        assert all(
            row["name"] == ""
            for row in players
        )

        # Cooldown applies independently to every seat in the batch.
        assert not enricher.submit_if_needed(
            observer,
            frame,
            2,
        )

        assert not enricher.submit_if_needed(
            observer,
            frame,
            8,
        )

        # At frame 9 all remain unresolved and become eligible
        # together again.
        assert enricher.submit_if_needed(
            observer,
            frame,
            9,
        )

        collect(enricher)

        assert CALLS == [
            expected,
            expected,
        ]

        print(
            "FAILED SEAT BLOCKS LATER SEATS: NO"
        )
        print(
            "IDENTITY SAME-FRAME BATCH FAIRNESS: PASS"
        )
        print(
            "V0.17 IDENTITY NO-SEAT-STARVATION: PASS"
        )

    finally:
        enricher.close()


if __name__ == "__main__":
    main()
