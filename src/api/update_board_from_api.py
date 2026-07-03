import json
import subprocess
from pathlib import Path
from src.api.live_hand_event_writer import set_board

ROOT = Path(__file__).resolve().parents[2]
BOARD_READER = ROOT / "src/api/board_api_reader.py"
BOARD_JSON = ROOT / "runtime/api/latest_board.json"

subprocess.run(["python3", str(BOARD_READER)], cwd=str(ROOT), check=True)

data = json.loads(BOARD_JSON.read_text())
board = data.get("board", [])

set_board(board)

print("Updated board from API:", board)
