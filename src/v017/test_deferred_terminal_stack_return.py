"""
V0.17 deferred terminal stack-return ownership.

A raw observed stack increase may arrive before authoritative
UNCONTESTED completion.

It has:
    - no wager authority;
    - no generic trusted-stack authority;
    - no terminal authority yet.

The raw observation must survive until independent semantic evidence
establishes UNCONTESTED completion. It may then be offered exactly once
to the existing strict terminal-return authority.
"""

from src.v017.frame_hand_observer import (
    FrameHandObserver,
)


PLAYERS = [
    {
        "seat": "hero",
        "position": "CO",
        "name": "Hero",
        "stack_bb": 50.0,
        "dealt_in": True,
        "is_hero": True,
    },
    {
        "seat": "bb",
        "position": "BB",
        "name": "BB",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
]


def build_observer():
    obs = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "hero",
            "bb",
        ],
        small_blind_seat="hero",
        big_blind_seat="bb",
        geometry={
            "hole_cards": {},
            "stack_regions": {},
        },
        trusted_stacks={
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=["bb"],
        quantitative_seats=[
            "hero",
            "bb",
        ],
        hero_seat="hero",
        hand_id="deferred-terminal-return",
    )

    # Close preflop.
    obs.hand.observe_stack_commitment(
        "hero",
        0.5,
    )
    obs.hand.observe_no_commitment(
        "bb"
    )

    obs.hand.start_street(
        "FLOP",
        [
            "bb",
            "hero",
        ],
        board=[
            "Jd",
            "9s",
            "Tc",
        ],
    )

    # BB checks. Hero bets 2.12.
    # BB has NOT folded yet.
    obs.hand.observe_no_commitment(
        "bb"
    )
    obs.hand.observe_stack_commitment(
        "hero",
        2.12,
    )

    # Physical stack after Hero's wager.
    obs.trusted_stacks["hero"] = 46.88

    return obs


def return_observation():
    return {
        "frame": 20,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "prior": 46.88,
        "reader_value": 49.00,
        "resolved": False,
        "resolved_value": None,
        "raw": [
            {
                "variant":
                    "native_green_psm7",
                "raw":
                    "49.00 BB",
                "stack_bb": 49.00,
            },
        ],
        "confidence": 0.8,
        "votes": 1,
        "mode": "native_green_fast",
    }


def main():
    obs = build_observer()
    observation = return_observation()

    assert not obs.hand.hand_complete

    actions_before = list(
        obs.hand.semantic_actions()
    )

    # No authority before terminal completion.
    assert (
        obs.admit_terminal_stack_return(
            observation
        )
        == ()
    )

    assert (
        obs.trusted_stacks["hero"]
        == 46.88
    )

    assert (
        obs.hand.semantic_actions()
        == actions_before
    )

    # Production must retain the raw upward observation without
    # granting it semantic or stack authority.
    obs.retain_terminal_stack_return(
        observation
    )

    assert (
        len(
            obs.pending_terminal_stack_returns
        )
        == 1
    )

    assert (
        obs.trusted_stacks["hero"]
        == 46.88
    )

    print(
        "PRE-TERMINAL RAW INCREASE RETAINED "
        "WITHOUT AUTHORITY: PASS"
    )

    # Independent semantic evidence now completes the hand.
    obs.hand.observe_fold(
        "bb"
    )

    assert obs.hand.hand_complete
    assert (
        obs.hand.completion_reason
        == "UNCONTESTED"
    )
    assert obs.hand.winner_seats == [
        "hero"
    ]

    # BB's fold is legitimate independent semantic evidence.
    # Snapshot chronology after that fold so this assertion tests
    # only that terminal accounting adds no betting action.
    actions_after_terminal_fold = list(
        obs.hand.semantic_actions()
    )

    emitted = (
        obs.reconcile_terminal_stack_returns()
    )

    assert len(emitted) == 1

    event = emitted[0]

    assert (
        event["type"]
        == "UNCALLED_RETURN_ADMITTED"
    )
    assert event["seat"] == "hero"
    assert event["amount_bb"] == 2.12
    assert event["prior"] == 46.88
    assert (
        event["resolved_value"]
        == 49.0
    )

    assert (
        obs.trusted_stacks["hero"]
        == 49.0
    )

    assert (
        obs.pending_terminal_stack_returns
        == []
    )

    assert (
        obs.hand.semantic_actions()
        == actions_after_terminal_fold
    )

    print(
        "AUTHORITATIVE UNCONTESTED RELEASE: PASS"
    )
    print(
        "DEFERRED UNCALLED RETURN ADMITTED: PASS"
    )
    print(
        "GENERIC BETTING ACTION APPENDED: NO"
    )
    print(
        "V0.17 DEFERRED TERMINAL STACK RETURN: PASS"
    )


if __name__ == "__main__":
    main()
