from dataclasses import dataclass, field
import cv2
import numpy as np
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEOM = json.load(open(ROOT / "config/geometry.json"))
CAPTURE = ROOT / "src/vision/window_capture.py"



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


class LocalEventDetector:
    def __init__(self):
        self.previous_frame = None

    def detect(self, frame):
        if self.previous_frame is None:
            self.previous_frame = frame
            return ChangeSet()

        changes = ChangeSet()

        for rect in GEOM["hero_cards"].values():
            if region_changed(self.previous_frame, frame, rect):
                changes.hero_changed = True
                break

        for rect in GEOM["board"].values():
            if region_changed(self.previous_frame, frame, rect):
                changes.board_changed = True
                break

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
