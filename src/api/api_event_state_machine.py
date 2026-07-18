from pathlib import Path
import json
import time
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
CURSOR = ROOT / "runtime/live/api_event_state_machine_cursor.txt"
STATE_PATH = ROOT / "runtime/live/api_event_state_machine_state.json"

from src.api.position_engine import assign_positions
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore
from src.state.betting_round_tracker import BettingRoundTracker


CANONICAL_STORE = CanonicalHandStore()


def canonical_load():
    return CANONICAL_STORE.load()


def canonical_save(hand):
    CANONICAL_STORE.save(hand)


def read_cursor():
    if CURSOR.exists():
        return int(CURSOR.read_text().strip() or "0")
    return 0


def save_cursor(n):
    CURSOR.write_text(str(n) + "\n")


def default_state():
    return {
        "phase": "WAITING",
        "hero_cards": [],
        "board": [],
        "hero_position": "unknown",
        "players": [],
        "dealer_button_seat": "",
        "positions": {},
        "hand_started_at": None,
        "hand_complete": False,
        "result": None,
        "hero_to_act": False,
        "forced_blinds_seeded": False,
        "timeline": [],
    }


def load_state():
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text())
        except Exception:
            state = default_state()
    else:
        state = default_state()

    for k, v in default_state().items():
        state.setdefault(k, v)

    return state


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def record_timeline(state, label):
    state.setdefault("timeline", []).append({
        "ts": time.time(),
        "phase": state.get("phase", "unknown"),
        "event": label,
    })
    return state



def normalize_card(card):
    if not isinstance(card, str):
        return card
    card = card.strip()
    if len(card) == 3 and card[:2] == "10":
        return "T" + card[2]
    return card


def normalize_cards(cards):
    return [normalize_card(c) for c in cards]


def transition_for_board_len(n):
    if n == 3:
        return "FLOP"
    if n == 4:
        return "TURN"
    if n == 5:
        return "RIVER"
    return None



def seed_forced_blinds(state, canonical):
    """
    Add mandatory SB and BB posts once per hand after authoritative
    positions become available.

    These are hand-initialization events, not inferred visual actions.
    """
    if state.get("phase") == "WAITING":
        return False

    if state.get("forced_blinds_seeded"):
        return False

    positions = state.get("positions") or {}

    sb_seat = next(
        (
            seat
            for seat, position in positions.items()
            if str(position).upper() == "SB"
        ),
        None,
    )
    bb_seat = next(
        (
            seat
            for seat, position in positions.items()
            if str(position).upper() == "BB"
        ),
        None,
    )

    if not sb_seat or not bb_seat:
        return False

    canonical.add_action(
        seat=sb_seat,
        action="POST_SMALL_BLIND",
        amount_bb=0.5,
        confidence=1.0,
        source="hand_initialization",
        evidence=["mandatory_blind_from_position"],
        ts=state.get("hand_started_at"),
    )
    canonical.add_action(
        seat=bb_seat,
        action="POST_BIG_BLIND",
        amount_bb=1.0,
        confidence=1.0,
        source="hand_initialization",
        evidence=["mandatory_blind_from_position"],
        ts=state.get("hand_started_at"),
    )

    state["forced_blinds_seeded"] = True

    print(
        f"[CANONICAL_INIT] SB={sb_seat} 0.5 BB "
        f"BB={bb_seat} 1.0 BB",
        flush=True,
    )
    return True


def handle_table_snapshot(state, event):
    players = event.get("players") or []
    dealer_button_seat = event.get("dealer_button_seat") or ""
    positions = assign_positions(players, dealer_button_seat)
    hero_position = positions.get("hero") or "unknown"

    state["players"] = players
    state["dealer_button_seat"] = dealer_button_seat
    state["positions"] = positions
    state["hero_position"] = hero_position

    if state.get("phase") != "WAITING":
        canonical = canonical_load()
        canonical.update_table_snapshot(
            players=players,
            hero_position=hero_position,
            positions=positions,
        )
        seed_forced_blinds(state, canonical)
        canonical_save(canonical)

    print("[STATE] table_snapshot", hero_position, f"players={len(players)}")
    return state



def handle_hero_cards(state, event):
    cards = normalize_cards(event.get("hero_cards") or [])

    if state["phase"] != "WAITING":
        print("[SKIP] hero_cards because phase is", state["phase"])
        return state

    if len(cards) != 2:
        print("[SKIP] invalid hero_cards", cards)
        return state

    state["phase"] = "PREFLOP"
    state["hero_cards"] = cards
    state["hand_started_at"] = event.get("ts") or time.time()
    state["hand_complete"] = False
    state["result"] = None
    state["forced_blinds_seeded"] = False

    canonical = CanonicalHand().start_hand(
        hand_id=f"live-{int(state['hand_started_at'] * 1000)}",
        players=state.get("players", []),
        hero_cards=cards,
        hero_position=state.get("hero_position", "unknown"),
        positions=state.get("positions", {}),
        started_ts=state["hand_started_at"],
    )
    canonical_save(canonical)

    state = record_timeline(state, f"hero_cards {' '.join(cards)}")
    print("[STATE] WAITING -> PREFLOP", cards)

    return state


def handle_board(state, event):
    board = normalize_cards(event.get("board") or [])
    n = len(board)

    if state["phase"] == "WAITING":
        print("[SKIP] board before hero_cards", board)
        return state

    if n not in (3, 4, 5):
        print("[SKIP] invalid board", board)
        return state

    if n <= len(state.get("board") or []):
        print("[SKIP] stale board", board)
        return state

    next_phase = transition_for_board_len(n)
    state["phase"] = next_phase
    state["board"] = board

    canonical = canonical_load()
    canonical.set_board(board)
    canonical_save(canonical)

    state = record_timeline(state, f"board {next_phase} {' '.join(board)}")
    print(f"[STATE] board -> {next_phase}", board)

    return state



def handle_hero_decision(state, event):
    if state["phase"] == "WAITING":
        return state

    state["hero_to_act"] = True
    state = record_timeline(state, f"hero_decision {state.get('phase')}")
    print("[STATE] hero_decision", state.get("phase"))
    return state


def handle_hero_action_complete(state, event):
    if state["phase"] == "WAITING":
        return state

    state["hero_to_act"] = False
    state = record_timeline(state, f"hero_action_complete {state.get('phase')}")
    print("[STATE] hero_action_complete", state.get("phase"))
    return state

def handle_inferred_action(state, event):
    if state.get("phase") == "WAITING":
        print("[SKIP] inferred_action while waiting", event)
        return state

    canonical = canonical_load()
    tracker = BettingRoundTracker(canonical)
    added = tracker.ingest(event)

    decision = tracker.decisions[-1] if tracker.decisions else None

    if added is None:
        if decision is not None:
            print(
                f"[CANONICAL_SKIP] {event.get('street')} "
                f"{event.get('seat')} {event.get('action')} "
                f"reason={decision.reason}"
            )
        return state

    canonical_save(canonical)

    print(
        f"[CANONICAL_ACTION] {added.street} {added.seat} "
        f"{added.action} confidence={added.confidence}"
    )

    state = record_timeline(
        state,
        f"canonical_action {added.street} "
        f"{added.seat} {added.action}",
    )

    return state


def handle_hand_complete(state, event):
    if state["phase"] == "WAITING":
        return state

    result = event.get("result") or "Hand complete"
    state["phase"] = "COMPLETE"
    state["hand_complete"] = True
    state["result"] = result

    state = record_timeline(state, f"hand_complete {result}")
    canonical = canonical_load()
    canonical.finish(
        result=result,
        ended_ts=event.get("ts") or time.time(),
    )
    canonical_save(canonical)

    archived = CANONICAL_STORE.archive()
    print(f"[ARCHIVE] {archived}")
    print("[STATE] -> COMPLETE", result)

    return default_state()


def handle_event(state, event):
    t = event.get("type")

    if t == "table_snapshot":
        return handle_table_snapshot(state, event)

    if t == "hero_cards":
        return handle_hero_cards(state, event)

    if t == "board":
        return handle_board(state, event)

    if t == "hero_decision":
        return handle_hero_decision(state, event)

    if t == "hero_action_complete":
        return handle_hero_action_complete(state, event)

    if t == "inferred_action":
        return handle_inferred_action(state, event)

    if t == "hand_complete":
        return handle_hand_complete(state, event)

    print("[SKIP] unknown event", event)
    return state


def main():
    print("api_event_state_machine running. Ctrl+C to stop.")

    while True:
        if not EVENT_LOG.exists():
            time.sleep(0.5)
            continue

        lines = EVENT_LOG.read_text().splitlines()
        cursor = read_cursor()
        state = load_state()

        for i in range(cursor, len(lines)):
            line = lines[i].strip()
            if not line:
                save_cursor(i + 1)
                continue

            event = json.loads(line)
            state = handle_event(state, event)
            save_state(state)
            save_cursor(i + 1)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
