import json
import shutil
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
FRAMES_DIR = RUNTIME / "current_hand_frames"
CROPS_DIR = RUNTIME / "debug_crops"
FAILED_HANDS_DIR = RUNTIME / "failed_hands"
LOGS_DIR = RUNTIME / "logs"
SESSION_LOG = LOGS_DIR / "session_log.jsonl"
CURRENT_STATE = ROOT / "current_hand_state.json"
CONFIG_PATH = ROOT / "config" / "runtime.json"


class HandPhase(str, Enum):
    WAITING_FOR_HAND = "WAITING_FOR_HAND"
    PREFLOP = "PREFLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    HAND_END = "HAND_END"


@dataclass
class LiveHandState:
    hand_id: Optional[str] = None
    phase: HandPhase = HandPhase.WAITING_FOR_HAND
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    hero_cards_seen: bool = False
    board_card_count: int = 0
    dealer_seat: Optional[int] = None
    hero_decision_visible: bool = False
    events: List[Dict[str, Any]] = field(default_factory=list)


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {
            "debug_mode": False,
            "keep_failed_hands": True,
            "cleanup_after_hand": True,
            "save_keyframes": True,
            "max_failed_hand_images": 20,
        }
    return json.loads(CONFIG_PATH.read_text())


def ensure_dirs() -> None:
    for path in [FRAMES_DIR, CROPS_DIR, FAILED_HANDS_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_session_event(event: Dict[str, Any]) -> None:
    ensure_dirs()
    with SESSION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def write_current_state(state: LiveHandState) -> None:
    payload = asdict(state)
    payload["phase"] = state.phase.value
    CURRENT_STATE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def new_hand_id() -> str:
    return time.strftime("hand_%Y%m%d_%H%M%S")


class LiveHandStateMachine:
    def __init__(self) -> None:
        ensure_dirs()
        self.config = load_config()
        self.state = LiveHandState(updated_at=time.time())
        write_current_state(self.state)

    def log_event(self, event_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        now = time.time()
        event = {
            "timestamp": now,
            "hand_id": self.state.hand_id,
            "phase": self.state.phase.value,
            "event": event_name,
            "details": details or {},
        }
        self.state.events.append(event)
        self.state.updated_at = now
        append_session_event(event)
        write_current_state(self.state)

    def start_hand(self, hero_cards_seen: bool = True, dealer_seat: Optional[int] = None) -> None:
        if self.state.phase != HandPhase.WAITING_FOR_HAND:
            return

        now = time.time()
        self.state = LiveHandState(
            hand_id=new_hand_id(),
            phase=HandPhase.PREFLOP,
            started_at=now,
            updated_at=now,
            hero_cards_seen=hero_cards_seen,
            dealer_seat=dealer_seat,
        )
        self.log_event("NEW_HAND", {"hero_cards_seen": hero_cards_seen, "dealer_seat": dealer_seat})

    def update_board_count(self, board_card_count: int) -> None:
        if self.state.phase == HandPhase.WAITING_FOR_HAND:
            return

        if board_card_count == self.state.board_card_count:
            return

        previous = self.state.board_card_count
        self.state.board_card_count = board_card_count

        if board_card_count == 0:
            next_phase = HandPhase.PREFLOP
        elif board_card_count == 3:
            next_phase = HandPhase.FLOP
        elif board_card_count == 4:
            next_phase = HandPhase.TURN
        elif board_card_count == 5:
            next_phase = HandPhase.RIVER
        else:
            next_phase = self.state.phase

        if next_phase != self.state.phase:
            self.state.phase = next_phase
            self.log_event("STREET_CHANGE", {"from_board_count": previous, "to_board_count": board_card_count})
        else:
            self.log_event("BOARD_COUNT_CHANGED", {"from_board_count": previous, "to_board_count": board_card_count})

    def set_hero_decision_visible(self, visible: bool, buttons: Optional[List[str]] = None) -> None:
        if self.state.phase == HandPhase.WAITING_FOR_HAND:
            return

        if visible == self.state.hero_decision_visible:
            return

        self.state.hero_decision_visible = visible
        if visible:
            self.log_event("HERO_DECISION_VISIBLE", {"buttons": buttons or []})
        else:
            self.log_event("HERO_DECISION_CLOSED", {})

    def end_hand(self, reason: str = "unknown", failed: bool = False) -> None:
        if self.state.phase == HandPhase.WAITING_FOR_HAND:
            return

        self.state.phase = HandPhase.HAND_END
        self.log_event("HAND_END", {"reason": reason, "failed": failed})

        if failed and self.config.get("keep_failed_hands", True):
            self.archive_failed_hand()

        if self.config.get("cleanup_after_hand", True):
            self.cleanup_temp_images()

        self.reset()

    def archive_failed_hand(self) -> None:
        if not self.state.hand_id:
            return

        target = FAILED_HANDS_DIR / self.state.hand_id
        target.mkdir(parents=True, exist_ok=True)

        for src_dir_name, src_dir in [("frames", FRAMES_DIR), ("crops", CROPS_DIR)]:
            if not src_dir.exists():
                continue
            dst = target / src_dir_name
            dst.mkdir(parents=True, exist_ok=True)
            for file in src_dir.glob("*"):
                if file.is_file():
                    shutil.copy2(file, dst / file.name)

    def cleanup_temp_images(self) -> None:
        for folder in [FRAMES_DIR, CROPS_DIR]:
            if folder.exists():
                for item in folder.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

    def reset(self) -> None:
        self.state = LiveHandState(updated_at=time.time())
        self.log_event("RESET", {})
        write_current_state(self.state)


if __name__ == "__main__":
    machine = LiveHandStateMachine()
    machine.start_hand(hero_cards_seen=True, dealer_seat=None)
    machine.update_board_count(3)
    machine.set_hero_decision_visible(True, ["Fold", "Call", "Raise"])
    machine.set_hero_decision_visible(False)
    machine.update_board_count(4)
    machine.update_board_count(5)
    machine.end_hand(reason="manual_test", failed=False)
    print("live_state_machine smoke test complete")
