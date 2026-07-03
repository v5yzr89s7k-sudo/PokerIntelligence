import json
import subprocess
from pathlib import Path
from src.api.live_hand_event_writer import new_hand

ROOT = Path(__file__).resolve().parents[2]
HERO_READER = ROOT / "src/api/hero_cards_api_reader.py"
HERO_JSON = ROOT / "runtime/api/latest_hero_cards.json"

subprocess.run(["python3", str(HERO_READER)], cwd=str(ROOT), check=True)

hero = json.loads(HERO_JSON.read_text())

players = [
    {"seat": "hero", "name": "Hero", "stack_bb": ""}
]

new_hand(
    players=players,
    hero_cards=hero.get("hero_cards", ["",""]),
    hero_position=""
)

print("Started hand from API")
