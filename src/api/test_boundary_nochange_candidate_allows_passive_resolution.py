from pathlib import Path
from tempfile import TemporaryDirectory

import src.api.api_event_state_machine as sm
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore


HAND = "boundary-nochange-passive-test"
STREET = "TURN"


def make_hand():
    players = [
        {
            "seat": "hero",
            "name": "Hero",
            "stack_bb": 6.90,
            "stack_text": "6.90 BB",
            "is_hero": True,
            "is_active": True,
        },
        {
            "seat": "seat_lower_left",
            "name": "Villain",
            "stack_bb": 44.20,
            "stack_text": "44.20 BB",
            "is_hero": False,
            "is_active": True,
        },
    ]

    positions = {
        "hero": "SB",
        "seat_lower_left": "BB",
    }

    hand = CanonicalHand().start_hand(
        hand_id=HAND,
        players=players,
        hero_cards=["Ah", "Kd"],
        hero_position="SB",
        positions=positions,
        started_ts=1.0,
    )

    hand.dealt_in_seats = [
        "hero",
        "seat_lower_left",
    ]
    hand.current_street = STREET
    hand.board = [
        "Jd",
        "9s",
        "Tc",
        "9h",
    ]

    # Heads-up postflop order: Hero acts before Villain.
    hand.players_to_act = [
        "hero",
        "seat_lower_left",
    ]

    return hand


def main():
    original_store = sm.CANONICAL_STORE
    original_active_tracker = sm._ACTIVE_TRACKER
    original_active_hand_id = sm._ACTIVE_HAND_ID

    with TemporaryDirectory() as tmp:
        try:
            sm.CANONICAL_STORE = CanonicalHandStore(
                json_path=Path(tmp) / "canonical.json",
                text_path=Path(tmp) / "current_hand.txt",
            )
            sm._ACTIVE_TRACKER = None
            sm._ACTIVE_HAND_ID = None

            hand = make_hand()
            sm.canonical_save(hand)

            state = sm.default_state()
            state.update({
                "phase": STREET,
                "hand_token": HAND,
                "canonical_snapshot_ready": True,
                "hero_position": "SB",
                "positions": {
                    "hero": "SB",
                    "seat_lower_left": "BB",
                },
                "dealt_in_seats": [
                    "hero",
                    "seat_lower_left",
                ],
                # The quantitative candidate is already gone:
                # repeated stack reads established no chip movement.
                "unresolved_stack_candidates": {},
            })

            tracker = sm.tracker_for_hand(
                sm.canonical_load()
            )

            before = list(
                sm.canonical_load().players_to_act
                or []
            )

            print("before:", before)

            # Reproduce the semantic state exposed by the real replay:
            #
            # - Hero is first to act on TURN.
            # - next-street board proves TURN ended.
            # - explicit retrospective boundary observation exists.
            # - that observation does not itself classify Hero's action.
            # - Hero's stack candidate has already closed with no
            #   validated quantitative transition.
            #
            # The unresolved observation must not permanently veto the
            # uniquely implied passive action.
            canonical = sm.canonical_load()

            state, resolved = (
                sm.resolve_silent_boundary_obligations(
                    state,
                    canonical=canonical,
                    tracker=tracker,
                    street=STREET,
                    observed_seats={"hero"},
                    reconsider_observed_after_candidate_release=True,
                )
            )

            checks = [
                action
                for action in canonical.actions
                if str(action.street).upper() == STREET
                and action.seat == "hero"
                and str(action.action).upper() == "CHECK"
            ]

            print(
                "resolved:",
                resolved,
            )
            print(
                "checks:",
                [
                    (
                        action.street,
                        action.seat,
                        action.action,
                    )
                    for action in checks
                ],
            )
            print(
                "remaining:",
                list(
                    canonical.players_to_act
                    or []
                ),
            )

            assert len(checks) == 1, (
                "RED: an explicit unresolved boundary observation "
                "still permanently blocks Hero's uniquely implied "
                "TURN CHECK after Hero's quantitative candidate has "
                "closed without a validated stack transition"
            )

            status_after = (
                tracker.commitment_tracker
                .round_status(STREET)
            )

            remaining_after = list(
                status_after.get("players_owing_action")
                or []
            )

            print(
                "tracker remaining:",
                remaining_after,
            )

            assert "hero" not in remaining_after, (
                "Hero passive resolution did not consume Hero's "
                "authoritative TURN obligation"
            )

            print(
                "PASS boundary no-change candidate release: "
                "non-quantitative explicit boundary evidence no "
                "longer vetoes a uniquely implied passive action "
                "after its quantitative blocker is definitively gone"
            )

        finally:
            sm.CANONICAL_STORE = original_store
            sm._ACTIVE_TRACKER = original_active_tracker
            sm._ACTIVE_HAND_ID = original_active_hand_id


if __name__ == "__main__":
    main()
