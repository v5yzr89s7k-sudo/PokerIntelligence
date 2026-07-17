from dataclasses import dataclass, field
import cv2
import numpy as np
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
GEOM = json.load(open(ROOT / "config/geometry.json"))
CAPTURE = ROOT / "src/vision/window_capture.py"

from src.events.detectors.hero_detector import hero_changed
from src.events.detectors.board_detector import board_changed
from src.events.detectors.pot_detector import pot_changed
from src.events.detectors.stack_detector import stack_changed, stack_change_details
from src.events.detectors.action_buttons_detector import action_buttons_changed, action_buttons_visible
from src.events.detectors.dealer_detector import dealer_changed
from src.events.detectors.card_presence import count_board_cards, hero_cards_visible
from src.events.detectors.hero_turn_detector import hero_nameplate_blinking
from src.events.detectors.bet_region_detector import bet_region_occupancy
from src.events.detectors.bet_region_state_tracker import BetRegionStateTracker
from src.events.detectors.frame_baseline import FrameBaseline
from src.events.transition_engine import TransitionEngine



def region_changed(previous, current, rect, threshold=8.0):
    x = rect["x"]
    y = rect["y"]
    w = rect["width"]
    h = rect["height"]

    a = previous[y:y+h, x:x+w]
    b = current[y:y+h, x:x+w]

    if a.shape != b.shape:
        return True

    diff = cv2.absdiff(a, b)
    return float(np.mean(diff)) > threshold


@dataclass
class ChangeSet:
    hero_changed: bool = False
    board_changed: bool = False
    pot_changed: bool = False
    dealer_changed: bool = False
    action_buttons_changed: bool = False
    action_buttons_visible: bool = False
    hero_nameplate_blinking: bool = False
    stack_changed_seats: list = field(default_factory=list)
    stack_change_details: dict = field(default_factory=dict)
    bet_region_occupancy: dict = field(default_factory=dict)
    occupied_bet_regions: list = field(default_factory=list)
    bet_region_transitions: dict = field(default_factory=dict)
    bet_region_appeared: list = field(default_factory=list)
    bet_region_cleared: list = field(default_factory=list)
    board_count: int = 0
    hero_cards_visible: bool = False
    hero_cards_transition: dict = field(default_factory=dict)
    hero_cards_appeared: bool = False
    hero_cards_cleared: bool = False

    def has_changes(self):
        return any([
            self.hero_changed,
            self.board_changed,
            self.pot_changed,
            self.dealer_changed,
            self.action_buttons_changed,
            self.action_buttons_visible,
            self.hero_nameplate_blinking,
            bool(self.stack_changed_seats),
            bool(self.bet_region_appeared),
            bool(self.bet_region_cleared),
            self.hero_cards_appeared,
            self.hero_cards_cleared,
        ])

    def to_dict(self):
        return {
            "hero_changed": self.hero_changed,
            "board_changed": self.board_changed,
            "pot_changed": self.pot_changed,
            "dealer_changed": self.dealer_changed,
            "action_buttons_changed": self.action_buttons_changed,
            "action_buttons_visible": self.action_buttons_visible,
            "hero_nameplate_blinking": self.hero_nameplate_blinking,
            "stack_changed_seats": list(self.stack_changed_seats),
            "stack_change_details": self.stack_change_details,
            "bet_region_occupancy": self.bet_region_occupancy,
            "occupied_bet_regions": list(self.occupied_bet_regions),
            "bet_region_transitions": self.bet_region_transitions,
            "bet_region_appeared": list(self.bet_region_appeared),
            "bet_region_cleared": list(self.bet_region_cleared),
            "board_count": self.board_count,
            "hero_cards_visible": self.hero_cards_visible,
            "hero_cards_transition": self.hero_cards_transition,
            "hero_cards_appeared": self.hero_cards_appeared,
            "hero_cards_cleared": self.hero_cards_cleared,
            "has_changes": self.has_changes(),
        }

    def summary(self):
        parts = []
        if self.hero_changed:
            parts.append("hero_changed")
        if self.board_changed:
            parts.append(f"board_changed/count={self.board_count}")
        if self.pot_changed:
            parts.append("pot_changed")
        if self.dealer_changed:
            parts.append("dealer_changed")
        if self.action_buttons_changed:
            parts.append("action_buttons_changed")
        if self.action_buttons_visible:
            parts.append("action_buttons_visible")
        if self.hero_nameplate_blinking:
            parts.append("hero_nameplate_blinking")
        if self.stack_changed_seats:
            parts.append("stack_changed=" + ",".join(self.stack_changed_seats))
        if self.occupied_bet_regions:
            parts.append("bet_regions=" + ",".join(self.occupied_bet_regions))
        if self.bet_region_appeared:
            parts.append("bet_region_appeared=" + ",".join(self.bet_region_appeared))
        if self.bet_region_cleared:
            parts.append("bet_region_cleared=" + ",".join(self.bet_region_cleared))
        if self.hero_cards_appeared:
            parts.append("hero_cards_appeared")
        if self.hero_cards_cleared:
            parts.append("hero_cards_cleared")
        return " ".join(parts) if parts else "no_change"


class LocalEventDetector:
    def __init__(self):
        self.previous_frame = None
        self.bet_region_tracker = BetRegionStateTracker()
        self.bet_region_baseline = FrameBaseline(
            pixel_threshold=18,
            blur_size=3,
        )
        self.transition_engine = TransitionEngine()

    def reset_bet_region_baseline(self, frame):
        self.bet_region_baseline.reset()
        self.bet_region_tracker.reset()

        for seat, rect in GEOM.get(
            "bet_regions",
            {},
        ).items():
            self.bet_region_baseline.capture(
                f"bet_region:{seat}",
                frame,
                rect,
            )

    def detect(self, frame):
        if self.previous_frame is None:
            self.previous_frame = frame
            self.reset_bet_region_baseline(frame)
            return ChangeSet()

        changes = ChangeSet()

        changes.hero_changed = hero_changed(self.previous_frame, frame, GEOM)
        changes.board_changed = board_changed(self.previous_frame, frame, GEOM)
        changes.pot_changed = pot_changed(self.previous_frame, frame, GEOM)
        changes.dealer_changed = dealer_changed(self.previous_frame, frame, GEOM)
        changes.action_buttons_changed = action_buttons_changed(self.previous_frame, frame, GEOM)
        changes.action_buttons_visible = action_buttons_visible(frame, GEOM)
        changes.stack_change_details = stack_change_details(self.previous_frame, frame, GEOM)
        changes.stack_changed_seats = [
            seat for seat, info in changes.stack_change_details.items()
            if info.get("changed")
        ]
        changes.bet_region_occupancy = bet_region_occupancy(
            frame,
            GEOM,
            baseline=self.bet_region_baseline,
        )
        changes.occupied_bet_regions = [
            seat for seat, info in changes.bet_region_occupancy.items()
            if info.get("occupied")
        ]
        changes.bet_region_transitions = self.bet_region_tracker.update(changes.bet_region_occupancy)
        changes.bet_region_appeared = [
            seat for seat, info in changes.bet_region_transitions.items()
            if info.get("appeared")
        ]
        changes.bet_region_cleared = [
            seat for seat, info in changes.bet_region_transitions.items()
            if info.get("cleared")
        ]
        changes.board_count = count_board_cards(frame, GEOM)
        changes.hero_cards_visible = hero_cards_visible(frame, GEOM)
        changes.hero_nameplate_blinking = hero_nameplate_blinking(self.previous_frame, frame, GEOM)

        changes = self.transition_engine.apply(changes)

        if changes.hero_cards_appeared:
            # New hand boundary. The previous hand's chips, cleared regions,
            # and debounce state must not carry into this hand.
            self.reset_bet_region_baseline(frame)

            # The current frame becomes the new baseline. Do not emit bet
            # transitions from the same frame used to establish it.
            changes.bet_region_occupancy = {}
            changes.occupied_bet_regions = []
            changes.bet_region_transitions = {}
            changes.bet_region_appeared = []
            changes.bet_region_cleared = []

        self.previous_frame = frame
        return changes


if __name__ == "__main__":
    import cv2

    captures = sorted(Path("runtime/window_captures").glob("acr_table_*.png"))

    if not captures:
        print("No captures found.")
    else:
        img = cv2.imread(str(captures[-1]))
        detector = LocalEventDetector()

        print("First frame:")
        print(detector.detect(img))

        input("\nChange the table, then press ENTER...")

        subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True)

        captures = sorted(Path("runtime/window_captures").glob("acr_table_*.png"))
        img2 = cv2.imread(str(captures[-1]))

        print("\nSecond frame:")
        print(detector.detect(img2))
