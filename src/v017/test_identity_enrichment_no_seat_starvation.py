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


def reader(frame, dealt_in_seats):
    # Deliberately resolve nobody.
    return {
        "players": [
            {
                "seat": dealt_in_seats[0],
                "name": "",
            }
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
        retry_frames=1,
    )

    frame = Path("/tmp/identity_fairness.png")

    try:
        attempted = []

        for frame_id in (1, 2, 3):
            assert enricher.submit_if_needed(
                observer,
                frame,
                frame_id,
            )

            attempted.append(
                enricher.seat
            )

            result = collect(enricher)

            assert result["name"] == ""

        print("attempted =", attempted)

        assert attempted == [
            "seat_top",
            "seat_mid_right",
            "seat_lower_right",
        ], (
            "identity scheduler did not provide "
            "deterministic round-robin fairness"
        )

        print(
            "FAILED SEAT BLOCKS LATER SEATS: NO"
        )
        print(
            "IDENTITY ROUND-ROBIN PROGRESS: PASS"
        )
        print(
            "V0.17 IDENTITY NO-SEAT-STARVATION: PASS"
        )

    finally:
        enricher.close()


if __name__ == "__main__":
    main()
