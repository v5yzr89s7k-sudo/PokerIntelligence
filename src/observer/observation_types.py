from dataclasses import dataclass, field, asdict
import time
from typing import Any, Dict, Optional


BOARD_CHANGED = "board_changed"
STACK_CHANGED = "stack_changed"
BET_REGION_OCCUPIED = "bet_region_occupied"
BET_REGION_CLEARED = "bet_region_cleared"
HERO_CARDS_VISIBLE = "hero_cards_visible"
HERO_CARDS_CLEARED = "hero_cards_cleared"
HERO_TURN_SIGNAL = "hero_turn_signal"
ACTION_BUTTONS_VISIBLE = "action_buttons_visible"
DEALER_CHANGED = "dealer_changed"
POT_CHANGED = "pot_changed"


@dataclass
class Observation:
    type: str
    ts: float = field(default_factory=time.time)
    street: str = "unknown"
    seat: Optional[str] = None
    confidence: float = 1.0
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            type=data.get("type", ""),
            ts=float(data.get("ts") or time.time()),
            street=data.get("street", "unknown"),
            seat=data.get("seat"),
            confidence=float(data.get("confidence", 1.0)),
            payload=data.get("payload") or {},
        )
