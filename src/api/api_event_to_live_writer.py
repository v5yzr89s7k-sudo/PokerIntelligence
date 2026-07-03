from pathlib import Path
import json
import time
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
CURSOR = ROOT / "runtime/live/api_event_writer_cursor.txt"

from src.api.live_hand_event_writer import new_hand, set_board


def read_cursor():
    if CURSOR.exists():
        return int(CURSOR.read_text().strip() or "0")
    return 0


def save_cursor(n):
    CURSOR.write_text(str(n))


def handle(event):
    t = event.get("type")

    if t == "hero_cards":
        cards = event.get("hero_cards") or []
        if len(cards) == 2:
            new_hand(players=[], hero_cards=cards, hero_position="unknown")
            print("[WRITE] hero_cards", cards)

    elif t == "board":
        board = event.get("board") or []
        if board:
            set_board(board)
            print("[WRITE] board", board)


def main():
    print("api_event_to_live_writer running. Ctrl+C to stop.")

    while True:
        if not EVENT_LOG.exists():
            time.sleep(0.5)
            continue

        lines = EVENT_LOG.read_text().splitlines()
        cursor = read_cursor()

        for i in range(cursor, len(lines)):
            event = json.loads(lines[i])
            handle(event)
            save_cursor(i + 1)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
