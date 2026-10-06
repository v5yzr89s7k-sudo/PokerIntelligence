from src.v017.run_live_observer import TemporalIdentityEnricher


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


def main():
    observer = Observer()

    enricher = TemporalIdentityEnricher(
        reader=lambda *args, **kwargs: None,
        retry_frames=8,
    )

    try:
        assert set(
            enricher.unresolved_seats(observer)
        ) == {
            "seat_lower_left",
            "seat_mid_left",
        }

        # Production contract to be implemented:
        # a visibly sitting-out seat is terminal for identity
        # enrichment during this hand.
        enricher.mark_terminal_identity_seat(
            "seat_lower_left",
            reason="sitting_out",
        )

        unresolved = enricher.unresolved_seats(
            observer
        )

        assert unresolved == [
            "seat_mid_left"
        ], unresolved

        assert (
            "seat_lower_left"
            in enricher.terminal_identity_seats
        )

        print("SITTING OUT IDENTITY RETRY: STOPPED")
        print("OTHER UNRESOLVED SEAT RETRY: PRESERVED")
        print("V0.17 SITTING-OUT IDENTITY TERMINAL: PASS")

    finally:
        enricher.close()


if __name__ == "__main__":
    main()
