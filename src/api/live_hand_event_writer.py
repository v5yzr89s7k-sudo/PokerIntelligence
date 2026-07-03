from pathlib import Path
from datetime import datetime
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "runtime/live/current_hand.txt"
STATE = ROOT / "runtime/live/current_hand_state.json"
HISTORY = ROOT / "runtime/history"
HISTORY.mkdir(parents=True, exist_ok=True)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def new_hand(players, hero_cards, hero_position):
    state = {
        "hand_started_at": now(),
        "hero_cards": hero_cards,
        "hero_position": hero_position,
        "players": players,
        "streets": {
            "preflop": [],
            "flop": [],
            "turn": [],
            "river": []
        },
        "board": [],
        "result": "",
        "hero_folded": False,
        "closed": False
    }
    save(state)
    render(state)

def load():
    return json.loads(STATE.read_text())

def save(state):
    STATE.write_text(json.dumps(state, indent=2))

def render(state):
    lines = []
    lines.append("CURRENT HAND")
    lines.append("=" * 60)
    lines.append(f"Started: {state['hand_started_at']}")
    lines.append("")
    lines.append("TABLE")
    lines.append("-" * 60)

    if state.get("dealer_button_seat"):
        lines.append(f"Dealer Button: {state['dealer_button_seat']}")
        lines.append("")

    hero_stack = ""

    for player in state["players"]:
        seat = player.get("seat","")
        name = player.get("name","")
        stack = player.get("stack_text") or (
            f"{player.get('stack_bb')} BB" if player.get("stack_bb") is not None else ""
        )

        if player.get("is_hero"):
            hero_stack = stack

        lines.append(f"{seat:<18} {name:<18} {stack}")

    lines.append("")
    lines.append(f"Hero Position: {state['hero_position']}")
    lines.append(f"Hero Stack: {hero_stack}")
    lines.append(f"Hero Cards: {' '.join(state['hero_cards'])}")
    lines.append("")

    lines.append("PREFLOP")
    lines.append("-" * 60)
    lines += state["streets"]["preflop"] or [""]

    if len(state["board"]) >= 3:
        lines.append("")
        lines.append(f"FLOP: {' '.join(state['board'][:3])}")
        lines.append("-" * 60)
        lines += state["streets"]["flop"] or [""]

    if len(state["board"]) >= 4:
        lines.append("")
        lines.append(f"TURN: {state['board'][3]}")
        lines.append("-" * 60)
        lines += state["streets"]["turn"] or [""]

    if len(state["board"]) >= 5:
        lines.append("")
        lines.append(f"RIVER: {state['board'][4]}")
        lines.append("-" * 60)
        lines += state["streets"]["river"] or [""]

    if state["hero_folded"]:
        lines.append("")
        lines.append("HERO FOLDED - LIVE STREET TRACKING STOPPED")

    if state["result"]:
        lines.append("")
        lines.append("RESULT")
        lines.append("-" * 60)
        lines.append(state["result"])

    LIVE.write_text("\n".join(lines) + "\n")


def set_table_snapshot(players, hero_position):
    state = load()
    state["players"] = players or state.get("players", [])
    if hero_position:
        state["hero_position"] = hero_position
    save(state)
    render(state)


def add_action(street, action):
    state = load()
    if state["hero_folded"]:
        return
    state["streets"][street].append(f"{now()} | {action}")
    if "hero folds" in action.lower() or "hero folded" in action.lower():
        state["hero_folded"] = True
        archive(state)
    save(state)
    render(state)

def set_board(board):
    state = load()
    state.setdefault("hero_folded", False)
    if state["hero_folded"]:
        return
    state["board"] = board
    save(state)
    render(state)

def close_hand(result):
    state = load()
    state["result"] = result
    state["closed"] = True
    save(state)
    render(state)
    archive(state)

def archive(state):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = HISTORY / f"hand_{ts}.txt"
    shutil.copy2(LIVE, dest)
    print(f"Archived {dest}")

if __name__ == "__main__":
    print("live_hand_event_writer loaded")
