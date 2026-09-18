from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ProductSnapshot:
    frame: int
    street: str
    action_count: int
    next_actor: Optional[str]
    text: str


@dataclass(frozen=True)
class ProgressionResult:
    snapshots: Tuple[ProductSnapshot, ...]
    final_text: str
