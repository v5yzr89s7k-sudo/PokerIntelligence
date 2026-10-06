from pathlib import Path

from src.v017.run_live_observer import (
    TemporalIdentityEnricher,
)


class Player:
    def __init__(self, name=""):
        self.name = name


class Hand:
    def __init__(self):
        self.players = {
            "hero": Player("Hero"),
            "seat_lower_left": Player(""),
            "seat_mid_left": Player(""),
        }


class Observer:
    hero_seat = "hero"

    def __init__(self):
        self.hand = Hand()


def reader(frame_path, dealt_in_seats=None):
    players = []

    for seat in dealt_in_seats or []:
        if seat == "seat_lower_left":
            players.append({
                "seat": seat,
                "name": "",
                "sitting_out": True,
            })
        else:
            players.append({
                "seat": seat,
                "name": "ResolvedPlayer",
                "sitting_out": False,
            })

    return {
        "players": players,
    }


def main():
    observer = Observer()

    enricher = TemporalIdentityEnricher(
        reader=reader,
        retry_frames=8,
    )

    try:
        frame = Path("/tmp/identity_sitting_out.png")
        frame.write_bytes(b"x")

        submitted = enricher.submit_if_needed(
            observer,
            frame,
            10,
        )

        assert submitted

        result = enricher.future.result()
        assert result

        # collect_ready requires the completed future.
        collected = enricher.collect_ready()
        assert collected is not None

        lower_left = next(
            row
            for row in collected["players"]
            if row["seat"] == "seat_lower_left"
        )

        assert lower_left["name"] == ""
        assert lower_left["sitting_out"] is True

        # Reproduce live application ownership.
        enricher.mark_terminal_identity_seat(
            "seat_lower_left",
            reason="sitting_out",
        )

        unresolved = enricher.unresolved_seats(
            observer
        )

        assert "seat_lower_left" not in unresolved
        assert "seat_mid_left" in unresolved

        print("SITTING-OUT SIGNAL PROPAGATED: PASS")
        print("LOWER-LEFT RESUBMISSION: STOPPED")
        print("OTHER UNRESOLVED RETRY: PRESERVED")
        print(
            "V0.17 SITTING-OUT RESULT LIFECYCLE: PASS"
        )

    finally:
        enricher.close()


if __name__ == "__main__":
    main()
