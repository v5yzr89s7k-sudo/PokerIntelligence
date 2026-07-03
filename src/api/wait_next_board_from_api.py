from pathlib import Path
import json, cv2, subprocess, time
from src.api.live_hand_event_writer import set_board

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "src/vision/window_capture.py"
CAPTURE_DIR = ROOT / "runtime/window_captures"
GEOM = json.load(open(ROOT / "config/geometry.json"))
BOARD_READER = ROOT / "src/api/board_api_reader.py"
BOARD_JSON = ROOT / "runtime/api/latest_board.json"
STATE = ROOT / "runtime/live/current_hand_state.json"

def current_confirmed_len():
    if not STATE.exists():
        return 0
    try:
        return len(json.loads(STATE.read_text()).get("board", []))
    except Exception:
        return 0

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

def local_board_count():
    img = cv2.imread(str(latest_capture()))
    img = cv2.resize(img, (934,696))
    return sum(
        1 for _,r in GEOM.get("board", {}).items()
        if card_present(crop(img,r))
    )

confirmed = current_confirmed_len()
print(f"Waiting for next board change. Confirmed board cards: {confirmed}. Ctrl+C to stop.")

stable_count = None
stable_seen = 0

while True:
    c = local_board_count()

    if c == stable_count:
        stable_seen += 1
    else:
        stable_count = c
        stable_seen = 1

    if stable_seen >= 6 and c in [3,4,5] and c > confirmed:
        print(f"Stable board count changed {confirmed} -> {c}. Calling API once.")
        subprocess.run(["python3", str(BOARD_READER)], cwd=str(ROOT), check=True)

        data = json.loads(BOARD_JSON.read_text())
        board = data.get("board", [])

        if len(board) > confirmed:
            set_board(board)
            print("Board updated:", board)
            break
        else:
            print("API did not confirm new board. Waiting locally again; no immediate repeat.")
            stable_seen = 0
            time.sleep(2)

    time.sleep(0.5)
