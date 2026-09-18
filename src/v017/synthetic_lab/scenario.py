from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class VisualStep:
    frame: int
    label: str
    expected_street: str
    expected_action_count: int
    expected_last_action: Optional[str] = None


@dataclass(frozen=True)
class Scenario:
    name: str
    steps: Tuple[VisualStep, ...]


JULY22_BASELINE = Scenario(
    name="july22_baseline",
    steps=(
        VisualStep(
            frame=1,
            label="initial physical table",
            expected_street="PREFLOP",
            expected_action_count=2,
        ),
        VisualStep(
            frame=38,
            label="preflop chronology established",
            expected_street="PREFLOP",
            expected_action_count=6,
        ),
        VisualStep(
            frame=52,
            label="preflop complete",
            expected_street="PREFLOP",
            expected_action_count=8,
        ),
        VisualStep(
            frame=90,
            label="flop",
            expected_street="FLOP",
            expected_action_count=9,
        ),
        VisualStep(
            frame=103,
            label="flop action",
            expected_street="FLOP",
            expected_action_count=12,
        ),
        VisualStep(
            frame=115,
            label="turn",
            expected_street="TURN",
            expected_action_count=14,
        ),
        VisualStep(
            frame=127,
            label="river",
            expected_street="RIVER",
            expected_action_count=15,
        ),
        VisualStep(
            frame=135,
            label="river action",
            expected_street="RIVER",
            expected_action_count=17,
        ),
    ),
)
