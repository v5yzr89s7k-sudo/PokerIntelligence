from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm

from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


def make_hand(hand_id):
    return CanonicalHand().start_hand(
        hand_id=hand_id,
        players=[
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "villain",
                "name": "Villain",
                "stack_bb": 50.0,
                "is_hero": False,
                "is_active": True,
            },
        ],
        hero_cards=["As", "Kd"],
        hero_position="SB",
        positions={
            "hero": "SB",
            "villain": "BB",
        },
        started_ts=1.0,
    )


def actions_for(hand, street):
    return [
        (action.seat, action.action)
        for action in hand.actions
        if action.street == street
    ]


def reset_tracker():
    sm._ACTIVE_TRACKER = None
    sm._ACTIVE_HAND_ID = None


def make_state(hand_token, phase):
    state = sm.default_state()

    state.update({
        "phase": phase,
        "hand_token": hand_token,
        "canonical_snapshot_ready": True,
    })

    return state


def main():
    original_store = sm.CANONICAL_STORE
    original_tracker = sm._ACTIVE_TRACKER
    original_hand_id = sm._ACTIVE_HAND_ID

    with TemporaryDirectory() as tmp:
        try:
            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=Path(tmp) / "canonical.json",
                text_path=Path(tmp) / "current_hand.txt",
            )

            # ====================================================
            # CASE A — MID-STREET ATTACHMENT
            #
            # Tracker is created after FLOP already exists.
            # Seeing Villain later must NOT author Hero CHECK.
            # ====================================================

            reset_tracker()

            hand = make_hand("midstreet-case")

            hand.set_board(
                ["Ac", "7d", "2s"],
                ts=2.0,
            )

            sm.canonical_save(hand)

            tracker = sm.tracker_for_hand(hand)

            print(
                "midstreet owns street start:",
                tracker.observed_street_start_owned,
            )

            assert (
                tracker.observed_street_start_owned
                is False
            )

            state = make_state(
                "midstreet-case",
                "FLOP",
            )

            state = sm.handle_actor_observed(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": "midstreet-case",
                    "street": "FLOP",
                    "seat": "villain",
                    "source": "bet_region_appeared",
                    "commitment_visible": True,
                    "blocked_seats": [],
                    "ts": 3.0,
                },
            )

            midstreet = sm.canonical_load()

            midstreet_actions = actions_for(
                midstreet,
                "FLOP",
            )

            print(
                "midstreet actions:",
                midstreet_actions,
            )

            assert (
                ("hero", "CHECK")
                not in midstreet_actions
            ), (
                "mid-street attachment fabricated Hero CHECK"
            )

            # ====================================================
            # CASE B — CONTINUOUS STREET OWNERSHIP
            #
            # Tracker exists on TURN before CanonicalHand advances
            # to RIVER. The same tracker therefore owns the RIVER
            # opening boundary.
            #
            # Villain begins acting while Hero is the preceding
            # outstanding no-commitment actor.
            #
            # Expected future behavior:
            # ActionTimeline resolves Hero CHECK before admitting
            # Villain's action.
            # ====================================================

            reset_tracker()

            hand = make_hand("continuous-case")

            hand.current_street = "TURN"
            hand.board = [
                "Ac",
                "7d",
                "2s",
                "9h",
            ]
            hand.players_to_act = []

            sm.canonical_save(hand)

            tracker = sm.tracker_for_hand(hand)

            tracker.commitment_tracker.reset_street(
                "TURN"
            )
            tracker.commitment_tracker.initialize_street_order(
                "TURN",
                ["hero", "villain"],
            )
            tracker.commitment_tracker.sync_queue(
                "TURN",
                [],
            )

            assert (
                tracker.observed_street_start_owned
                is False
            )

            # Simulate the canonical board transition while the
            # persistent tracker already exists.
            hand.set_board(
                [
                    "Ac",
                    "7d",
                    "2s",
                    "9h",
                    "3c",
                ],
                ts=11.0,
            )

            sm.canonical_save(hand)

            tracker = sm.tracker_for_hand(hand)

            print(
                "continuous owns street start:",
                tracker.observed_street_start_owned,
            )

            print(
                "before actor queue:",
                hand.players_to_act,
            )

            assert (
                tracker.observed_street_start_owned
                is True
            )

            assert hand.players_to_act == [
                "hero",
                "villain",
            ]

            state = make_state(
                "continuous-case",
                "RIVER",
            )

            state = sm.handle_actor_observed(
                state,
                {
                    "type": "actor_observed",
                    "hand_token": "continuous-case",
                    "street": "RIVER",
                    "seat": "villain",
                    "source": "bet_region_appeared",
                    "commitment_visible": True,
                    "blocked_seats": [],
                    "ts": 12.0,
                },
            )

            continuous = sm.canonical_load()

            river_actions = actions_for(
                continuous,
                "RIVER",
            )

            print(
                "continuous RIVER actions:",
                river_actions,
            )

            print(
                "after actor queue:",
                continuous.players_to_act,
            )

            assert (
                ("hero", "CHECK")
                in river_actions
            ), (
                "RED: owned postflop street did not resolve "
                "the completed no-commitment predecessor as "
                "CHECK through the canonical action owner"
            )

            assert (
                continuous.players_to_act
                and continuous.players_to_act[0]
                == "villain"
            ), (
                "observed Villain did not become live actor "
                "after predecessor resolution"
            )

            print()
            print(
                "PASS: continuously observed postflop "
                "chronology resolves only its owned "
                "no-commitment predecessor"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_tracker
            sm._ACTIVE_HAND_ID = original_hand_id


if __name__ == "__main__":
    main()
