import json, subprocess, time
from pathlib import Path
from src.api.live_hand_event_writer import set_board

ROOT = Path(__file__).resolve().parents[2]
BOARD_READER = ROOT / "src/api/board_api_reader.py"
BOARD_JSON = ROOT / "runtime/api/latest_board.json"

last_board = []

print("Watching for board. Ctrl+C to stop.")

try:
    while True:
        subprocess.run(["python3", str(BOARD_READER)], cwd=str(ROOT), check=True)
        data = json.loads(BOARD_JSON.read_text())
        board = data.get("board", [])

        if board and board != last_board:
            set_board(board)
            print("Board updated:", board)
            last_board = board

        time.sleep(8)
except KeyboardInterrupt:
    print("Stopped.")
