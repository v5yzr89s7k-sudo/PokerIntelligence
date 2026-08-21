from dataclasses import dataclass

from src.state.betting_round_tracker import (
    BettingRoundTracker,
)


@dataclass
class Player:
    active: bool = True
    folded: bool = False
    all_in: bool = False


class FakeHand:
    def __init__(self):
        self.current_street = "FLOP"
        self.current_bet_bb = 3.37
        self.last_aggressor_seat = "bb"
        self.players_to_act = [
            "btn",
            "hero",
        ]
        self.players = {
            "btn": Player(),
            "hero": Player(),
        }
        self.actions = []

    def add_action(
        self,
        *,
        seat,
        action,
        confidence,
        source,
        evidence,
        ts=None,
        **kwargs,
    ):
        item = type(
            "Action",
            (),
            {
                "street": self.current_street,
                "seat": seat,
                "action": action,
            },
        )()

        self.actions.append(item)

        if action == "FOLD":
            self.players[seat].folded = True
            self.players[seat].active = False

        return item


class FakeCommitmentTracker:
    def consume_pending_action(self, *args, **kwargs):
        pass

    def record_action(self, *args, **kwargs):
        pass

    def record_response(self, *args, **kwargs):
        pass

    def sync_queue(self, *args, **kwargs):
        pass


def make_tracker(hand):
    tracker = BettingRoundTracker.__new__(
        BettingRoundTracker
    )

    tracker.hand = hand
    tracker.commitment_tracker = (
        FakeCommitmentTracker()
    )
    tracker.has_open_bet = True

    return tracker


def main():
    # Direct physical evidence for the queue head is admissible.
    hand = FakeHand()
    tracker = make_tracker(hand)

    added = tracker.resolve_physically_completed_actor(
        "btn",
        ts=1.0,
    )

    assert len(added) == 1
    assert added[0].seat == "btn"
    assert added[0].action == "FOLD"
    assert hand.players_to_act == ["hero"]

    # Physical evidence for a later actor may NOT jump the head.
    hand = FakeHand()
    tracker = make_tracker(hand)

    added = tracker.resolve_physically_completed_actor(
        "hero",
        ts=2.0,
    )

    assert added == []
    assert hand.players_to_act == [
        "btn",
        "hero",
    ]
    assert hand.actions == []

    print(
        "PASS physical actor resolution: "
        "head-only evidence resolves normally; "
        "later-seat evidence cannot jump chronology"
    )


if __name__ == "__main__":
    main()
