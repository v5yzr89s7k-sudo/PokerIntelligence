from pathlib import Path
import json, cv2, subprocess, time
from src.api.live_hand_event_writer import set_board

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))
BOARD_READER = ROOT / "src/api/board_api_reader.py"
BOARD_JSON = ROOT / "runtime/api/latest_board.json"

def latest_capture():
    subprocess.run(["python3", str(CAPTURE)], cwd=str(ROOT),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return sorted(CAPTURE_DIR.glob("acr_table_*.png"))[-1]

def crop(img, r):
    x,y,w,h = map(int,[r["x"],r["y"],r["width"],r["height"]])
    return img[y:y+h,x:x+w]

def card_present(c):
    gray = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    return (gray > 145).mean() > 0.08

def board_count():
    img = cv2.imread(str(latest_capture()))
    img = cv2.resize(img, (934,696))
    count = 0
    for name,r in GEOM.get("board", {}).items():
        if card_present(crop(img,r)):
            count += 1
    return count

last_count = 0
last_api_board = []
last_api_len = 0
last_api_len = 0

print("Watching board locally. API only on 0→3, 3→4, 4→5. Ctrl+C to stop.")

try:
    while True:
        c = board_count()

        if c in [3,4,5] and c != last_count:
            print(f"Board count changed {last_count} -> {c}. Calling board API once.")
            subprocess.run(["python3", str(BOARD_READER)], cwd=str(ROOT), check=True)
            data = json.loads(BOARD_JSON.read_text())
            board = data.get("board", [])

            if board and board != last_api_board:
                set_board(board)
                last_api_board = board
                last_api_len = len(board)
                print("Board updated:", board)

        # If local detector says more cards than API confirmed, keep checking.
        if c > last_api_len:
            last_count = last_api_len
        else:
            last_count = c
        time.sleep(0.5)

except KeyboardInterrupt:
    print("Stopped.")
