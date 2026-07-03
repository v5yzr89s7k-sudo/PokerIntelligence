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
from src.events.detectors.stack_detector import stack_changed
from src.events.detectors.action_buttons_detector import action_buttons_changed
from src.events.detectors.dealer_detector import dealer_changed
from src.events.detectors.card_presence import count_board_cards, hero_cards_visible



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
    stack_changed_seats: list = field(default_factory=list)
    board_count: int = 0
    hero_cards_visible: bool = False

    def has_changes(self):
        return any([
            self.hero_changed,
            self.board_changed,
            self.pot_changed,
            self.dealer_changed,
            self.action_buttons_changed,
            bool(self.stack_changed_seats),
        ])


class LocalEventDetector:
    def __init__(self):
        self.previous_frame = None

    def detect(self, frame):
        if self.previous_frame is None:
            self.previous_frame = frame
            return ChangeSet()

        changes = ChangeSet()

        changes.hero_changed = hero_changed(self.previous_frame, frame, GEOM)
        changes.board_changed = board_changed(self.previous_frame, frame, GEOM)
        changes.pot_changed = pot_changed(self.previous_frame, frame, GEOM)
        changes.dealer_changed = dealer_changed(self.previous_frame, frame, GEOM)
        changes.action_buttons_changed = action_buttons_changed(self.previous_frame, frame, GEOM)
        changes.stack_changed_seats = stack_changed(self.previous_frame, frame, GEOM)
        changes.board_count = count_board_cards(frame, GEOM)
        changes.hero_cards_visible = hero_cards_visible(frame, GEOM)

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
