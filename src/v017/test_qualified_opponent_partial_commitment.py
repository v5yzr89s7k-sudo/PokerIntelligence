
from src.v017.frame_hand_observer import FrameHandObserver


def observation(frame, value):
    return {
        "frame": frame,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "villain",
        "resolved": True,
        "resolved_value": value,
        "settlement_confirmed": True,
    }


def main():
    observer = FrameHandObserver(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
            },
            {
                "seat": "villain",
                "position": "BB",
                "name": "Villain",
                "stack_bb": 50.0,
            },
        ],
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={"hole_cards": {}, "stack_regions": {}},
        trusted_stacks={
            "hero": 50.0,
            "villain": 50.0,
        },
        opponent_seats=["villain"],
        quantitative_seats=["hero", "villain"],
        hero_seat="hero",
        hand_id="qualified-opponent-partial",
    )

    # Hero establishes a 3 BB price.
    raised = observer.admit_quantitative_observation({
        "frame": 9,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": 47.5,
        "settlement_confirmed": True,
    })

    assert raised
    assert observer.hand.current_price_bb == 3.0
    assert observer.hand.next_actor == "villain"

    # Independent physical bet-region appearance establishes
    # a bounded opponent quantitative episode.
    observer.quantitative_retry_pending["villain"] = {
        "attempts": 1,
        "first_frame": 10,
        "last_frame": 10,
        "commitment_seen": True,
        "reason": "bet_region_appearance",
        "actor_at_first_motion": "villain",
        "street": "PREFLOP",
    }

    # Villain already posted 1 BB. A further 1 BB is
    # insufficient to reach the 3 BB price.
    partial = observer.admit_quantitative_observation(
        observation(11, 49.0)
    )

    assert not partial

    # RED: the confirmed intermediate measurement must not
    # destroy the original cumulative reference while the
    # independently established episode remains active.
    assert observer.trusted_stacks["villain"] == 50.0, (
        "RED: QUALIFIED PARTIAL BASELINE LOST",
        observer.trusted_stacks["villain"],
    )

    completed = observer.admit_quantitative_observation(
        observation(12, 48.0)
    )

    calls = [
        row
        for row in observer.hand.semantic_actions()
        if row["seat"] == "villain"
        and row["action"] == "CALL"
    ]

    assert completed
    assert len(calls) == 1, calls


    # A stale retry must not retain a below-price baseline.
    stale = FrameHandObserver(
        players=[
            {
                "seat": "hero",
                "position": "SB",
                "name": "Hero",
                "stack_bb": 50.0,
                "is_hero": True,
            },
            {
                "seat": "villain",
                "position": "BB",
                "name": "Villain",
                "stack_bb": 50.0,
            },
        ],
        action_order=["hero", "villain"],
        small_blind_seat="hero",
        big_blind_seat="villain",
        geometry={"hole_cards": {}, "stack_regions": {}},
        trusted_stacks={"hero": 50.0, "villain": 50.0},
        opponent_seats=["villain"],
        quantitative_seats=["hero", "villain"],
        hero_seat="hero",
        hand_id="expired-opponent-ownership",
    )

    raised = stale.admit_quantitative_observation({
        "frame": 9,
        "type": "STACK_QUANTITATIVE_OBSERVATION",
        "seat": "hero",
        "resolved": True,
        "resolved_value": 47.5,
        "settlement_confirmed": True,
    })

    assert raised
    assert stale.hand.next_actor == "villain"

    stale.quantitative_retry_pending["villain"] = {
        "attempts": stale.quantitative_retry_max_attempts,
        "first_frame": 10,
        "last_frame": 10,
        "commitment_seen": True,
        "reason": "bet_region_appearance",
        "actor_at_first_motion": "villain",
        "street": "PREFLOP",
    }

    rejected = stale.admit_quantitative_observation(
        observation(11, 49.0)
    )

    assert not rejected
    assert stale.trusted_stacks["villain"] == 49.0, (
        "EXPIRED OPPONENT RETAINED STALE BASELINE"
    )

    print("EXPIRED OPPONENT OWNERSHIP: PASS")

    print("QUALIFIED OPPONENT PARTIAL COMMITMENT: PASS")


if __name__ == "__main__":
    main()
