"""
Regression: a chronology-blocked predecessor must not cause a later actor to
be classified against stale canonical betting price.

Controlled preflop state:

    canonical current price = 1.0 BB
    Hero/SB prior live commitment = 0.5 BB

    authoritative unresolved queue:
        UTG -> BTN -> Hero -> BB

BTN then has trusted quantitative evidence of a 2.0 BB commitment. Because
UTG remains unresolved, BTN cannot yet enter canonical betting state, so
CanonicalHand.current_bet_bb remains 1.0 BB.

Hero subsequently has trusted CALL_OR_RAISE evidence with delta 1.5 BB.
Hero's total live commitment is therefore 2.0 BB.

If BTN's preceding 2.0 BB aggression were authoritative betting context,
Hero is calling to 2.0 BB.

The resolver must not classify Hero as RAISE merely because canonical
current_bet_bb is still the stale 1.0 BB price.
"""

from src.state.betting_round_tracker import (
    BettingRoundTracker,
)
from src.state.canonical_hand import CanonicalHand


def make_hand():
    hand = CanonicalHand().start_hand(
        hand_id="blocked-price-regression",
        players=[
            {
                "seat": "utg",
                "name": "UTG",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "btn",
                "name": "BTN",
                "stack_bb": 100.0,
                "is_active": True,
            },
            {
                "seat": "hero",
                "name": "Hero",
                "stack_bb": 100.0,
                "is_hero": True,
                "is_active": True,
            },
            {
                "seat": "bb",
                "name": "BB",
                "stack_bb": 100.0,
                "is_active": True,
            },
        ],
        hero_cards=["Ah", "Qd"],
        hero_position="SB",
        positions={
            "utg": "UTG",
            "btn": "BTN",
            "hero": "SB",
            "bb": "BB",
        },
        started_ts=1.0,
    )

    hand.current_street = "PREFLOP"

    # Canonical betting state has only the forced-blind price.
    hand.current_bet_bb = 1.0

    # Hero already owns the 0.5 BB small blind contribution.
    hand.players["hero"].committed_by_street[
        "PREFLOP"
    ] = 0.5

    # BB's forced contribution is included for realistic state, although
    # this regression concerns BTN -> Hero pricing.
    hand.players["bb"].committed_by_street[
        "PREFLOP"
    ] = 1.0

    # UTG deliberately remains unresolved ahead of BTN.
    hand.players_to_act = [
        "utg",
        "btn",
        "hero",
        "bb",
    ]

    return hand


def event(
    *,
    episode_id,
    seat,
    action,
    delta_bb,
):
    return {
        "episode_id": episode_id,
        "street": "PREFLOP",
        "seat": seat,
        "action": action,
        "confidence": 0.99,
        "evidence": [
            "test_stack_transition",
        ],
        "ts": float(episode_id),
        "measurements": {
            "stack_change": {
                "delta_bb": delta_bb,
                "stack_read_confidence": 0.99,
                "stack_read_mode": (
                    "agreement_verified"
                ),
            }
        },
    }


def main():
    hand = make_hand()
    tracker = BettingRoundTracker(hand)

    tracker.commitment_tracker.sync_queue(
        "PREFLOP",
        [
            "utg",
            "btn",
            "hero",
            "bb",
        ],
    )

    print("===== INITIAL STATE =====")
    print(
        "canonical_current_bet_bb =",
        hand.current_bet_bb,
    )
    print(
        "hero_prior_commitment_bb =",
        hand.players[
            "hero"
        ].committed_by_street[
            "PREFLOP"
        ],
    )
    print(
        "owing =",
        tracker.commitment_tracker
        .players_owing_action(
            "PREFLOP"
        ),
    )

    # ------------------------------------------------------------
    # BTN has quantitative evidence establishing a 2.0 BB commitment,
    # but UTG remains unresolved ahead of BTN.
    # ------------------------------------------------------------

    btn = tracker.resolve_inferred_action(
        event(
            episode_id=101,
            seat="btn",
            action="BET_OR_RAISE",
            delta_bb=2.0,
        )
    )

    print()
    print("===== BTN RESOLUTION =====")
    print(btn)

    assert btn["resolved"] is False, (
        "setup failure: BTN unexpectedly chronology-admitted"
    )

    assert (
        btn["reason"]
        == "earlier actors remain unresolved"
    ), btn

    assert btn.get("action") == "RAISE", (
        "setup failure: BTN quantitative evidence did not "
        "establish raise-sized commitment"
    )

    assert hand.current_bet_bb == 1.0, (
        "setup failure: chronology-blocked BTN mutated "
        "canonical betting price"
    )

    # BTN's action existence is already externally owned and its trusted
    # stack evidence establishes a total 2.0 BB commitment. Record that
    # quantitative pricing fact without admitting BTN canonically.
    tracker.commitment_tracker.record_pending_quantitative_commitment(
        "PREFLOP",
        "btn",
        2.0,
    )

    effective_price = (
        tracker.commitment_tracker.effective_price_before(
            "PREFLOP",
            "hero",
            canonical_price=hand.current_bet_bb,
        )
    )

    print()
    print(
        "effective_price_before_hero =",
        effective_price,
    )

    assert effective_price == 2.0, (
        "RED: pending predecessor quantitative commitment "
        "did not establish Hero's effective price"
    )

    # ------------------------------------------------------------
    # Hero/SB now loses another 1.5 BB.
    #
    # Prior live commitment = 0.5.
    # New total commitment  = 2.0.
    #
    # Against BTN's preceding 2.0 BB commitment this is a CALL.
    # Against stale canonical price 1.0 BB the current resolver may
    # incorrectly call it a RAISE.
    # ------------------------------------------------------------

    hero = tracker.resolve_inferred_action(
        event(
            episode_id=102,
            seat="hero",
            action="CALL_OR_RAISE",
            delta_bb=1.5,
        )
    )

    print()
    print("===== HERO RESOLUTION =====")
    print(hero)

    print()
    print(
        "canonical_current_bet_bb =",
        hand.current_bet_bb,
    )
    print(
        "hero_prior_live_commitment_bb =",
        hero.get(
            "prior_live_commitment_bb"
        ),
    )
    print(
        "hero_target_commitment_bb =",
        hero.get(
            "target_commitment_bb"
        ),
    )
    print(
        "hero_action =",
        hero.get("action"),
    )
    print(
        "hero_reason =",
        hero.get("reason"),
    )

    # The unresolved resolver response intentionally discards its internal
    # sizing fields today, so establish the quantitative ground truth from
    # the controlled hand state instead of relying on those returned fields.
    hero_prior_live_commitment_bb = float(
        hand.players[
            "hero"
        ].committed_by_street[
            "PREFLOP"
        ]
    )

    hero_delta_bb = 1.5

    hero_target_commitment_bb = round(
        hero_prior_live_commitment_bb
        + hero_delta_bb,
        2,
    )

    print(
        "ground_truth_prior_live_commitment_bb =",
        hero_prior_live_commitment_bb,
    )
    print(
        "ground_truth_target_commitment_bb =",
        hero_target_commitment_bb,
    )

    assert (
        hero_prior_live_commitment_bb
        == 0.5
    ), (
        "setup failure: Hero prior live commitment "
        "must be 0.5 BB"
    )

    assert (
        hero_target_commitment_bb
        == 2.0
    ), (
        "setup failure: Hero target commitment "
        "must be 2.0 BB"
    )

    assert hand.current_bet_bb == 1.0

    assert effective_price == 2.0

    assert hero.get("action") != "RAISE", (
        "RED: Hero was classified as RAISE from stale "
        "canonical current_bet_bb=1.0 even though the "
        "chronology-blocked predecessor had already "
        "established a 2.0 BB effective price"
    )

    assert hero.get("action") == "CALL", (
        "RED: Hero should resolve as CALL against the "
        "pending predecessor price of 2.0 BB"
    )

    print()
    print(
        "PASS: chronology-blocked predecessor quantitative price "
        "correctly classifies later Hero action as CALL"
    )


if __name__ == "__main__":
    main()
