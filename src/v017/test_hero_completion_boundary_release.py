"""
Behavioral regression for the live Hero-completion / street-boundary
deadlock.

Production composition under test:

    Hero buttons disappear
        -> quantitative ownership exists
        -> first post-action stack observation
        -> independent later-frame confirmation
        -> normal StackSettlementGate settlement
        -> normal quantitative semantic admission
        -> Hero action complete
        -> subsequent FLOP boundary can advance

No board boundary is allowed to invent an under-price Hero action.
No post-boundary quantitative evidence is used to repair PREFLOP.
"""

from pathlib import Path
from threading import Event

import numpy as np

from src.v017.frame_hand_observer import (
    FrameHandObserver,
    FrameObservationResult,
)

import src.v017.run_live_observer as live


PLAYERS = [
    {
        "seat": "raiser",
        "position": "BTN",
        "name": "Raiser",
        "stack_bb": 50.0,
        "dealt_in": True,
    },
    {
        "seat": "hero",
        "position": "SB",
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


def hero_quantitative(frame, value):
    return {
        "frame": frame,
        "type":
            "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "prior": 50.0,
        "reader_value": value,
        "resolved": True,
        "resolved_value": value,
        "candidates": (
            (value, 1),
        ),
        "confidence": 0.80,
        "votes": 1,
        "mode": "native_green_fast",
        "physical_delta_bb": (
            50.0 - value
        ),
    }


def build_observer():
    observer = FrameHandObserver(
        players=PLAYERS,
        action_order=[
            "raiser",
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
            "raiser": 50.0,
            "hero": 50.0,
            "bb": 50.0,
        },
        opponent_seats=[],
        quantitative_seats=[
            "hero",
        ],
        hero_seat="hero",
        hand_id=(
            "hero-completion-"
            "quantitative-deadlock-release"
        ),
    )

    hand = observer.hand

    # BTN raises to 3 BB.
    assert (
        hand.observe_stack_commitment(
            "raiser",
            3.0,
        )
        == "RAISE"
    )

    # Hero is now authoritative and below the price:
    # SB has 0.5 BB committed, price is 3 BB.
    assert hand.street == "PREFLOP"
    assert hand.next_actor == "hero"
    assert hand.current_price_bb == 3.0

    return observer


def frame_result(frame_id, events):
    return FrameObservationResult(
        frame_id=frame_id,
        events=tuple(events),
        changed=False,
        text=None,
    )


def run_transaction(
    observer,
    state,
    expected_frame_id,
    events,
):
    original = observer.process_frame

    def fake_process_frame(
        image,
        frame_id=None,
        sensor_frame=None,
        sensor_geometry=None,
    ):
        assert frame_id == expected_frame_id

        return frame_result(
            expected_frame_id,
            events,
        )

    observer.process_frame = fake_process_frame

    try:
        image = np.zeros(
            (
                696,
                934,
                3,
            ),
            dtype=np.uint8,
        )

        return live.process_frame_transaction(
            observer,
            image,
            Path(
                f"/tmp/"
                f"hero_deadlock_{expected_frame_id}.png"
            ),
            expected_frame_id,
            state,
        )

    finally:
        observer.process_frame = original


def main():
    observer = build_observer()
    state = live.FrameTransactionState()

    # Hero became physically actionable earlier in the hand.
    # The live defect is that this sensor remains stale True
    # after Hero acts, so no BUTTONS_DISAPPEARED event arrives.
    state.hero_buttons_active = True

    original_board_reader = (
        live.read_board_identity
    )

    board_release = Event()

    def board_reader(
        frame_path,
        expected_count,
    ):
        assert expected_count == 3

        if not board_release.wait(
            timeout=5.0
        ):
            raise RuntimeError(
                "board release timeout"
            )

        return [
            "Jd",
            "9s",
            "Tc",
        ]

    live.read_board_identity = board_reader

    try:
        before = len(
            observer.hand.semantic_actions()
        )

        assert observer.hand.street == "PREFLOP"
        assert observer.hand.next_actor == "hero"
        assert observer.hand.current_price_bb == 3.0

        # ----------------------------------------------------
        # FRAME 20
        #
        # Hero has physically acted, but the button sensor is
        # stale-visible and therefore emits no disappearance.
        #
        # The first post-action stack observation exists in the
        # same physical frame as the objective FLOP boundary.
        #
        # Current production has no Hero-completion ownership
        # here, so this is the red lifecycle.
        # ----------------------------------------------------

        tx20 = run_transaction(
            observer,
            state,
            20,
            (
                hero_quantitative(
                    20,
                    47.5,
                ),
                {
                    "frame": 20,
                    "type":
                        "FLOP_BOUNDARY_PHYSICAL",
                    "board_count": 3,
                    "previous_board_count": 0,
                },
            ),
        )

        assert tx20.outcome == "CONTINUE"

        print(
            "hero_completion_pending_frame =",
            state.hero_completion_pending_frame,
        )

        print(
            "hero_buttons_active =",
            state.hero_buttons_active,
        )

        print(
            "next_actor_after_boundary =",
            observer.hand.next_actor,
        )

        print(
            "settlement_candidate =",
            state.settlement_gate.pending.get(
                "hero"
            ),
        )

        assert (
            state.hero_completion_pending_frame
            == 20
        ), (
            "confirmed next-street physical boundary "
            "did not establish Hero completion "
            "opportunity while stale buttons remained "
            "visible"
        )

        # Boundary must not fabricate semantic action.
        assert (
            len(observer.hand.semantic_actions())
            == before
        )

        assert observer.hand.next_actor == "hero"

        candidate = (
            state.settlement_gate.pending.get(
                "hero"
            )
        )

        assert candidate is not None
        assert candidate.value == 47.5
        assert candidate.first_frame == 20

        print(
            "BOUNDARY ESTABLISHED HERO COMPLETION "
            "OPPORTUNITY WITHOUT INVENTING ACTION: PASS"
        )

        # ----------------------------------------------------
        # FRAME 21
        #
        # Independent quantitative confirmation now resolves
        # through the existing settlement/admission path.
        # ----------------------------------------------------

        tx21 = run_transaction(
            observer,
            state,
            21,
            (
                hero_quantitative(
                    21,
                    47.5,
                ),
            ),
        )

        assert tx21.outcome == "CONTINUE"

        actions = (
            observer.hand.semantic_actions()
        )

        new_actions = actions[before:]

        assert len(new_actions) == 1

        hero_action = new_actions[0]

        assert hero_action["seat"] == "hero"

        assert observer.hand.next_actor == "bb"

        assert (
            state.hero_completion_pending_frame
            is None
        )

        assert (
            "hero"
            not in state.settlement_gate.pending
        )

        print(
            "NORMAL HERO QUANTITATIVE SETTLEMENT "
            "RELEASED FRONTIER: PASS"
        )

        # Remaining BB action is independently physical.
        folded = (
            observer.admit_card_disappearance(
                "bb",
                frame_id=21,
                physical_type=(
                    "OPPONENT_CARDS_DISAPPEARED"
                ),
            )
        )

        assert folded
        assert observer.hand.next_actor is None

        # The frame-20 boundary was already queued. Identity
        # remains asynchronous and must now be allowed to apply.
        assert (
            state.board_identity_reader.future
            is not None
        )

        board_release.set()

        completed = None

        for _ in range(100):
            completed = (
                state.board_identity_reader
                .collect_ready()
            )

            if completed is not None:
                break

            Event().wait(0.01)

        assert completed is not None

        applied = (
            live.apply_async_board_identity_result(
                observer,
                completed,
            )
        )

        assert applied is True

        assert observer.hand.street == "FLOP"

        assert observer.hand.board == [
            "Jd",
            "9s",
            "Tc",
        ]

        assert (
            observer.pending_street_boundaries
            == []
        )

        print(
            "RETAINED FLOP ADVANCED AFTER HERO "
            "RELEASE: PASS"
        )

        print(
            "V0.17 HERO COMPLETION BOUNDARY "
            "RELEASE: PASS"
        )

    finally:
        board_release.set()
        state.board_identity_reader.close()
        live.read_board_identity = (
            original_board_reader
        )


if __name__ == "__main__":
    main()
