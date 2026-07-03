from pathlib import Path
import sys
import time
import subprocess
import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"

from src.events.local_event_detector import LocalEventDetector


def capture_latest():
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    latest = sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]
    return cv2.imread(str(latest))


def main():
    detector = LocalEventDetector()
    print("Watching local events. Ctrl+C to stop.")

    last_printed = None

    while True:
        frame = capture_latest()
        changes = detector.detect(frame)

        signature = repr(changes)

        if signature != last_printed and any([
            changes.hero_changed,
            changes.board_changed,
            changes.pot_changed,
            changes.dealer_changed,
            changes.action_buttons_changed,
            bool(changes.stack_changed_seats),
        ]):
            print(changes)
            last_printed = signature

        time.sleep(0.5)


if __name__ == "__main__":
    main()
