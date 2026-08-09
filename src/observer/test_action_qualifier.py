from dataclasses import dataclass

from src.observer.action_qualifier import ActionQualifier


@dataclass
class FakeAction:
    seat: str
    street: str
    action: str
    confidence: float
    evidence: list


qualifier = ActionQualifier()


immature_episode = {
    "episode_id": 4,
    "seat": "seat_mid_left",
    "street": "PREFLOP",
    "evidence_mature": False,
    "maturity_reason": "no_quantitative_stack_commitment",
}

immature_action = FakeAction(
    seat="seat_mid_left",
    street="PREFLOP",
    action="UNKNOWN",
    confidence=0.45,
    evidence=[
        "bet_region_occupied",
        "pot_changed",
    ],
)

decision = qualifier.qualify(
    immature_episode,
    immature_action,
)

assert decision.episode_id == 4
assert decision.seat == "seat_mid_left"
assert decision.street == "PREFLOP"

# ACTION must remain explicit through qualification.
assert decision.action == "UNKNOWN"
assert decision.confidence == 0.45

assert decision.evidence_mature is False
assert (
    decision.maturity_reason
    == "no_quantitative_stack_commitment"
)

# An UNKNOWN candidate without quantitative commitment evidence is not
# allowed into canonical publication.
assert decision.publish is False
assert (
    decision.qualification_reason
    == "retire_immature_unknown"
)


mature_episode = {
    "episode_id": 5,
    "seat": "hero",
    "street": "FLOP",
    "evidence_mature": True,
    "maturity_reason": "quantitative_stack_commitment",
}

mature_action = FakeAction(
    seat="hero",
    street="FLOP",
    action="BET_OR_RAISE",
    confidence=0.80,
    evidence=[
        "bet_region_occupied",
        "stack_changed",
    ],
)

decision = qualifier.qualify(
    mature_episode,
    mature_action,
)

assert decision.action == "BET_OR_RAISE"
assert decision.evidence_mature is True
assert decision.publish is True
assert (
    decision.qualification_reason
    == "publish_candidate_action"
)

# Non-chip actions must not be rejected merely because STACK_CHANGED is
# absent. Action-specific qualification remains explicit.
passive_episode = {
    "episode_id": 6,
    "seat": "seat_upper_right",
    "street": "FLOP",
    "evidence_mature": False,
    "maturity_reason": "no_quantitative_stack_commitment",
}

passive_action = FakeAction(
    seat="seat_upper_right",
    street="FLOP",
    action="CHECK",
    confidence=0.80,
    evidence=[
        "bet_region_occupied",
    ],
)

passive_decision = qualifier.qualify(
    passive_episode,
    passive_action,
)

assert passive_decision.action == "CHECK"
assert passive_decision.evidence_mature is False
assert passive_decision.publish is True
assert (
    passive_decision.qualification_reason
    == "publish_candidate_action"
)

serialized = decision.to_dict()

assert serialized["action"] == "BET_OR_RAISE"
assert serialized["publish"] is True

print("ActionQualifier evidence-gate regression passed.")
