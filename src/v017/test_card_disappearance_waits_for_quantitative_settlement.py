from src.v017.hand_engine import HandEngine
from src.v017.frame_hand_observer import FrameHandObserver


def main():
    players = [
        {
            "seat": "hero",
            "position": "CO",
            "name": "Hero",
            "stack_bb": 8.62,
        },
        {
            "seat": "villain",
            "position": "BB",
            "name": "Villain",
            "stack_bb": 16.46,
        },
        {
            "seat": "sb",
            "position": "SB",
            "name": "SB",
            "stack_bb": 50.0,
        },
    ]

    hand = HandEngine(
        players,
        ["hero", "sb", "villain"],
        small_blind_seat="sb",
        big_blind_seat="villain",
    )

    observer = FrameHandObserver.__new__(FrameHandObserver)
    observer.hand = hand
    observer.hero_seat = "hero"
    observer.events = []
    observer.pending_card_disappearances = []
    observer.pending_quantitative_evidence = []
    observer.pending_street_boundaries = []
    observer.quantitative_retry_pending = {}
    observer.quantitative_confirmation_pending = {}
    observer.unresolved_quantitative_motion = {}
    observer.pre_boundary_stack_motion = {}
    observer.trusted_stacks = {
        "hero": 8.62,
        "villain": 15.46,
        "sb": 49.5,
    }

    # Hero shoves and SB folds, leaving Villain facing the shove.
    hand.observe_stack_commitment(
        "hero",
        8.62,
        all_in_confirmed=True,
    )
    hand.observe_cards_disappeared("sb")

    assert hand.next_actor == "villain"

    # Strong physical stack motion has armed quantitative ownership,
    # but OCR still shows Villain's old stack.
    observer.quantitative_retry_pending["villain"] = {
        "reason": "stack_motion",
        "attempts": 1,
        "baseline": 15.46,
    }

    observer.retain_card_disappearance(
        "villain",
        frame_id=35,
    )

    before = tuple(hand.semantic_actions())

    reconciled = (
        observer.reconcile_pending_card_disappearances()
    )

    assert reconciled == (), reconciled
    assert tuple(hand.semantic_actions()) == before
    assert hand.next_actor == "villain"
    assert len(observer.pending_card_disappearances) == 1

    print(
        "CARD DISAPPEARANCE WAITS FOR "
        "QUANTITATIVE SETTLEMENT: PASS"
    )

    # Settlement resolves to the called amount.
    observer.quantitative_retry_pending.pop(
        "villain",
        None,
    )

    emitted = observer.admit_quantitative_observation(
        {
            "frame": 36,
            "type": "STACK_QUANTITATIVE_OBSERVATION",
            "seat": "villain",
            "resolved": True,
            "resolved_value": 7.84,
            "settlement_first_frame": 34,
        }
    )

    actions = [
        row
        for row in hand.semantic_actions()
        if (
            row["seat"] == "villain"
            and row["action"] not in {
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        )
    ]

    assert emitted, emitted
    assert len(actions) == 1, actions
    assert actions[0]["action"] == "CALL", actions

    # The CALL closes betting because Hero is already all-in.
    # The retained disappearance is therefore showdown cleanup,
    # not future FOLD authority.
    assert hand.next_actor is None

    observer.pending_card_disappearances = [
        row
        for row in observer.pending_card_disappearances
        if row.get("seat") != "villain"
    ]

    villain_folds = [
        row
        for row in hand.semantic_actions()
        if (
            row["seat"] == "villain"
            and row["action"] == "FOLD"
        )
    ]

    assert villain_folds == [], villain_folds
    assert not observer.pending_card_disappearances

    print(
        "SETTLED CALL WINS OVER CARD DISAPPEARANCE: PASS"
    )
    print(
        "SHOWDOWN CARD CLEANUP CANNOT BECOME FOLD: PASS"
    )


if __name__ == "__main__":
    main()
