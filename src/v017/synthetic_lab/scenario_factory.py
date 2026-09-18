from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ScenarioPlayer:
    seat: str
    position: str
    name: str
    stack_bb: float
    is_hero: bool = False


@dataclass(frozen=True)
class PhysicalEvidence:
    frame: int
    type: str

    seat: Optional[str] = None

    prior: Optional[float] = None
    value: Optional[float] = None

    confidence: float = 0.80
    votes: int = 1
    mode: str = "native_green_fast"

    street: Optional[str] = None
    board: Tuple[str, ...] = ()

    all_in_physical: bool = False


@dataclass(frozen=True)
class ExpectedAction:
    street: str
    seat: str
    action: str
    amount_bb: Optional[float] = None
    raise_to_bb: Optional[float] = None


@dataclass(frozen=True)
class ExpectedPublication:
    frame: int
    street: str
    action_count: int
    next_actor: Optional[str]

    required_text: Tuple[str, ...] = ()
    forbidden_text: Tuple[str, ...] = ()
    forbidden_text_after: Tuple[
        Tuple[str, str],
        ...
    ] = ()


@dataclass(frozen=True)
class FactoryScenario:
    name: str

    players: Tuple[ScenarioPlayer, ...]
    action_order: Tuple[str, ...]

    small_blind_seat: str
    big_blind_seat: str
    hero_seat: str

    evidence: Tuple[PhysicalEvidence, ...]

    expected_actions: Tuple[ExpectedAction, ...]
    expected_publications: Tuple[
        ExpectedPublication,
        ...
    ]

    # A scenario may intentionally exercise only a fragment of a hand.
    expected_final_street: str = "PREFLOP"


def validate_scenario(scenario):
    seats = tuple(
        player.seat
        for player in scenario.players
    )

    assert seats, "scenario requires players"
    assert len(seats) == len(set(seats)), (
        "duplicate player seat"
    )

    heroes = tuple(
        player.seat
        for player in scenario.players
        if player.is_hero
    )

    assert heroes == (scenario.hero_seat,), (
        "scenario must contain exactly one matching Hero"
    )

    assert scenario.small_blind_seat in seats
    assert scenario.big_blind_seat in seats
    assert scenario.hero_seat in seats

    assert set(
        scenario.action_order
    ).issubset(set(seats))

    frames = tuple(
        item.frame
        for item in scenario.evidence
    )

    assert frames == tuple(sorted(frames)), (
        "physical evidence must be chronological"
    )

    publication_frames = tuple(
        item.frame
        for item in scenario.expected_publications
    )

    assert publication_frames == tuple(
        sorted(publication_frames)
    ), (
        "expected publications must be chronological"
    )

    action_counts = tuple(
        item.action_count
        for item in scenario.expected_publications
    )

    assert action_counts == tuple(
        sorted(action_counts)
    ), (
        "publication action counts cannot regress"
    )

    for action in scenario.expected_actions:
        assert action.seat in seats

    return scenario
