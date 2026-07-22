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
from src.api.participant_validation_recorder import (
    record_participant_comparison,
)


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
        "level": {},
        "dealt_in_seats": [],
        "hand_token": "",
        "participant_frame_count": 0,
        "participant_validation_recorded": False,
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
    Add mandatory antes, SB, and BB once per hand after authoritative
    positions and the dealt-in hand roster are available.

    All contribution amounts are normalized to big blinds.
    """
    if state.get("phase") == "WAITING":
        return False

    if state.get("forced_blinds_seeded"):
        return False

    positions = state.get("positions") or {}
    dealt_in_seats = list(
        state.get("dealt_in_seats") or []
    )
    level = state.get("level") or {}

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

    small_blind_bb = float(
        level.get("small_blind_bb")
        if level.get("small_blind_bb") is not None
        else 0.5
    )
    big_blind_bb = float(
        level.get("big_blind_bb")
        if level.get("big_blind_bb") is not None
        else 1.0
    )
    ante_bb = float(level.get("ante_bb") or 0.0)

    # Antes belong only to players dealt into this hand. This roster is
    # immutable for the duration of the hand and does not shrink on folds.
    if ante_bb > 0.0:
        for seat in dealt_in_seats:
            if seat not in canonical.players:
                continue

            canonical.add_action(
                seat=seat,
                action="POST_ANTE",
                amount_bb=ante_bb,
                confidence=1.0,
                source="hand_initialization",
                evidence=["mandatory_ante_from_tournament_level"],
                ts=state.get("hand_started_at"),
            )

    canonical.add_action(
        seat=sb_seat,
        action="POST_SMALL_BLIND",
        amount_bb=small_blind_bb,
        confidence=1.0,
        source="hand_initialization",
        evidence=["mandatory_blind_from_position"],
        ts=state.get("hand_started_at"),
    )
    canonical.add_action(
        seat=bb_seat,
        action="POST_BIG_BLIND",
        amount_bb=big_blind_bb,
        confidence=1.0,
        source="hand_initialization",
        evidence=["mandatory_blind_from_position"],
        ts=state.get("hand_started_at"),
    )

    canonical.current_bet_bb = big_blind_bb
    canonical.last_aggressor_seat = None

    # Starting Pot must be available immediately from mandatory
    # contributions, before the asynchronous observed-pot OCR returns.
    forced_pot_bb = float(canonical.expected_pot_bb or 0.0)

    preflop_summary = canonical.street_summaries.get("PREFLOP")
    if preflop_summary is not None:
        # This value is derived from the tournament level frozen for this hand:
        # dealt-in antes + SB + BB. It must be available immediately and must
        # never temporarily regress to None/unknown.
        preflop_summary.starting_pot_bb = forced_pot_bb
        preflop_summary.ending_pot_bb = forced_pot_bb

    # Seed the live pot from deterministic forced contributions. A later
    # pot_update event may replace this with the authoritative observed pot.
    if canonical.pot_bb is None:
        canonical.pot_bb = forced_pot_bb

    state["forced_blinds_seeded"] = True

    print(
        f"[CANONICAL_INIT] antes={len(dealt_in_seats)}x{ante_bb:g} BB "
        f"SB={sb_seat} {small_blind_bb:g} BB "
        f"BB={bb_seat} {big_blind_bb:g} BB "
        f"pot={float(canonical.pot_bb or 0.0):g} BB",
        flush=True,
    )
    return True

def handle_table_snapshot(state, event):
    players = event.get("players") or []
    dealt_in_seats = state.get("dealt_in_seats") or []
    snapshot_dealt_in_seats = list(
        event.get("dealt_in_seats") or []
    )

    event_hand_token = str(
        event.get("hand_token") or ""
    )
    state_hand_token = str(
        state.get("hand_token") or ""
    )

    if (
        not state.get("participant_validation_recorded")
        and dealt_in_seats
        and snapshot_dealt_in_seats
        and event_hand_token
        and (
            not state_hand_token
            or event_hand_token == state_hand_token
        )
    ):
        validation = record_participant_comparison(
            hand_token=event_hand_token,
            local_dealt_in=dealt_in_seats,
            snapshot_dealt_in=snapshot_dealt_in_seats,
            local_frame_count=state.get(
                "participant_frame_count"
            ),
            recorded_ts=event.get("ts") or time.time(),
        )

        if validation.get("recorded"):
            state["participant_validation_recorded"] = True

            record = validation.get("record") or {}
            summary = validation.get("summary") or {}

            print(
                "[PARTICIPANT_VALIDATION] "
                f"match={record.get('exact_match')} "
                f"local={record.get('local_dealt_in')} "
                f"snapshot={record.get('snapshot_dealt_in')} "
                f"missing={record.get('missing_locally')} "
                f"extra={record.get('extra_locally')} "
                f"hands={summary.get('hands_compared')} "
                f"accuracy={summary.get('accuracy_percent')}%",
                flush=True,
            )
        else:
            print(
                "[PARTICIPANT_VALIDATION_SKIP] "
                f"reason={validation.get('reason')}",
                flush=True,
            )
    elif (
        snapshot_dealt_in_seats
        and event_hand_token
        and state_hand_token
        and event_hand_token != state_hand_token
    ):
        print(
            "[PARTICIPANT_VALIDATION_SKIP] "
            "reason=hand_token_mismatch "
            f"state={state_hand_token[:8]} "
            f"event={event_hand_token[:8]}",
            flush=True,
        )

    dealer_button_seat = state.get("dealer_button_seat") or ""
    positions = state.get("positions") or {}
    hero_position = state.get("hero_position") or "unknown"

    state["players"] = players

    if state.get("phase") != "WAITING":
        canonical = canonical_load()

        canonical.update_table_snapshot(
            players=players,
            hero_position=hero_position,
            positions=positions,
            dealt_in_seats=dealt_in_seats,
        )

        # The canonical hand must still be PREFLOP here so mandatory
        # contributions are never attached to FLOP/TURN/RIVER.
        canonical.current_street = "PREFLOP"

        seed_forced_blinds(state, canonical)

        state["canonical_snapshot_ready"] = True
        canonical_save(canonical)

        pending = list(state.get("pending_board_events") or [])
        state["pending_board_events"] = []

        for pending_event in pending:
            pending_board = normalize_cards(
                pending_event.get("board") or []
            )

            if len(pending_board) not in (3, 4, 5):
                continue

            if len(pending_board) <= len(state.get("board") or []):
                continue

            next_phase = transition_for_board_len(
                len(pending_board)
            )

            state["phase"] = next_phase
            state["board"] = pending_board

            canonical.set_board(
                pending_board,
                ts=pending_event.get("ts") or time.time(),
            )

            state = record_timeline(
                state,
                f"board {next_phase} {' '.join(pending_board)}",
            )

            print(
                f"[STATE] replayed buffered board -> "
                f"{next_phase} {pending_board}",
                flush=True,
            )

        canonical_save(canonical)

    print("[STATE] table_snapshot", hero_position, f"players={len(players)}")
    return state



def handle_table_context(state, event):
    """
    Accept the coordinator-owned immutable roster and position context.

    The asynchronous table snapshot may later enrich names and starting
    stacks, but it may not redefine the current hand's participants,
    dealer, positions, or Hero position.
    """
    dealt_in_seats = list(event.get("dealt_in_seats") or [])
    positions = dict(event.get("positions") or {})
    dealer_button_seat = event.get("dealer_button_seat") or ""
    hero_position = event.get("hero_position") or positions.get("hero") or "unknown"

    if not dealt_in_seats:
        print("[SKIP] table_context has no dealt-in seats", flush=True)
        return state

    event_players = {
        item.get("seat"): item
        for item in (event.get("players") or [])
        if isinstance(item, dict)
        and item.get("seat") in dealt_in_seats
    }

    players = []

    for seat in dealt_in_seats:
        local = event_players.get(seat) or {}

        players.append({
            "seat": seat,
            "name": local.get("name") or seat,
            "stack_bb": local.get("stack_bb"),
            "stack_text": local.get("stack_text") or "",
            "stack_confidence": local.get("stack_confidence"),
            "stack_read_mode": local.get("stack_read_mode") or "unknown",
            "is_hero": seat == "hero",
            "is_active": True,
        })

    state["players"] = players
    state["dealt_in_seats"] = dealt_in_seats
    state["hand_token"] = str(
        event.get("hand_token") or ""
    )
    state["participant_frame_count"] = int(
        event.get("participant_frame_count") or 0
    )
    state["participant_validation_recorded"] = False
    state["dealer_button_seat"] = dealer_button_seat
    state["positions"] = positions
    state["hero_position"] = hero_position

    print(
        f"[STATE] table_context "
        f"dealer={dealer_button_seat or 'unknown'} "
        f"hero_position={hero_position} "
        f"players={len(dealt_in_seats)}",
        flush=True,
    )

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
    state["level"] = dict(event.get("level") or {})
    # table_context is the authoritative prerequisite for live poker state.
    # Snapshot OCR is enrichment only and must not delay the hand.
    state["canonical_snapshot_ready"] = bool(
        state.get("dealt_in_seats")
        and state.get("positions")
    )
    state["pending_board_events"] = []

    canonical = CanonicalHand().start_hand(
        hand_id=f"live-{int(state['hand_started_at'] * 1000)}",
        players=state.get("players", []),
        hero_cards=cards,
        hero_position=state.get("hero_position", "unknown"),
        positions=state.get("positions", {}),
        started_ts=state["hand_started_at"],
    )

    canonical.dealt_in_seats = list(
        state.get("dealt_in_seats") or []
    )

    seed_forced_blinds(state, canonical)
    canonical_save(canonical)

    state = record_timeline(state, f"hero_cards {' '.join(cards)}")
    print("[STATE] WAITING -> PREFLOP", cards)

    return state


def handle_stack_update(state, event):
    if state.get("phase") == "WAITING":
        print("[SKIP] stack_update while waiting")
        return state

    seat = event.get("seat")
    current_stack_bb = event.get("current_stack_bb")

    if not seat or current_stack_bb is None:
        print("[SKIP] invalid stack_update", event)
        return state

    canonical = canonical_load()
    result = canonical.update_player_stack(
        seat=seat,
        new_stack_bb=float(current_stack_bb),
    )

    if result is None:
        print(f"[SKIP] stack_update unknown seat={seat}")
        return state

    canonical_save(canonical)

    print(
        f"[CANONICAL_STACK] seat={seat} "
        f"previous={result.get('previous_stack_bb')} "
        f"current={result.get('current_stack_bb')} "
        f"delta={result.get('delta_bb')}",
        flush=True,
    )

    return state


def handle_pot_update(state, event):
    """
    Validate an observed ACR pot before allowing it to mutate CanonicalHand.

    The canonical commitment total is authoritative for live publication.
    OCR remains corroborating evidence and may not overwrite the hand when it
    materially conflicts with recorded actions.
    """
    if state.get("phase") == "WAITING":
        print("[SKIP] pot_update while waiting")
        return state

    pot_bb = event.get("pot_bb")

    if pot_bb is None:
        print("[SKIP] invalid pot_update", event)
        return state

    try:
        observed = round(float(pot_bb), 2)
    except (TypeError, ValueError):
        print("[SKIP] invalid pot_update", event)
        return state

    if not 0.1 <= observed <= 1000.0:
        print(f"[SKIP] out-of-range pot_update pot={observed}")
        return state

    canonical = canonical_load()
    expected = canonical.expected_pot_bb

    # Without a canonical commitment total, preserve the observation only in
    # logs. Do not publish an unvalidated OCR value into current_hand.txt.
    if expected is None:
        print(
            f"[POT_REJECTED] observed={observed:.2f} "
            "expected=unknown reason=no_canonical_commitment_total",
            flush=True,
        )
        return state

    expected = round(float(expected), 2)
    difference = round(observed - expected, 2)

    # Allow only small OCR/rounding variance. Materially conflicting readings
    # remain diagnostic observations and cannot mutate CanonicalHand.
    tolerance_bb = 0.25

    if abs(difference) > tolerance_bb:
        print(
            f"[POT_REJECTED] observed={observed:.2f} "
            f"expected={expected:.2f} "
            f"difference={difference:.2f} "
            "reason=inconsistent_with_canonical_commitments",
            flush=True,
        )
        return state

    accepted = canonical.set_observed_pot(observed)
    canonical_save(canonical)

    print(
        f"[CANONICAL_POT] accepted={accepted:.2f} "
        f"expected={expected:.2f} "
        f"difference={difference:.2f}",
        flush=True,
    )

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

    if not state.get("canonical_snapshot_ready"):
        pending = list(state.get("pending_board_events") or [])

        pending.append({
            "board": board,
            "ts": event.get("ts") or time.time(),
        })

        pending.sort(
            key=lambda item: (
                len(item.get("board") or []),
                float(item.get("ts") or 0.0),
            )
        )

        state["pending_board_events"] = pending

        print(
            f"[STATE] buffered board len={n} "
            f"waiting_for_snapshot",
            flush=True,
        )

        return state

    next_phase = transition_for_board_len(n)
    state["phase"] = next_phase
    state["board"] = board

    canonical = canonical_load()
    canonical.set_board(
        board,
        ts=event.get("ts") or time.time(),
    )
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

def handle_hero_fold(state, event):
    if state.get("phase") == "WAITING":
        return state

    canonical = canonical_load()

    already_recorded = any(
        action.seat == canonical.hero_seat
        and action.street == canonical.current_street
        and action.action == "FOLD"
        for action in canonical.actions
    )

    if not already_recorded:
        added = canonical.add_action(
            seat=canonical.hero_seat,
            action="FOLD",
            confidence=1.0,
            source="hero_card_disappearance",
            evidence=[
                "hero_action_complete",
                "hero_cards_cleared",
            ],
            ts=event.get("ts") or time.time(),
        )
        canonical_save(canonical)

        print(
            f"[CANONICAL_ACTION] {added.street} "
            f"{added.seat} FOLD confidence=1.0"
        )

    state["hero_to_act"] = False
    state = record_timeline(
        state,
        f"hero_fold {event.get('street') or state.get('phase')}",
    )
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


VALIDATION_SUMMARY_PATH = (
    Path(__file__).resolve().parents[2]
    / "runtime/live/validation_summary.txt"
)


def write_validation_summary(canonical, archived):
    """
    Write a compact operational summary for the most recently completed hand.

    Detailed detector diagnostics remain in the console log. This file reports
    only the information needed for routine hand validation.
    """
    data = canonical.to_dict()

    players = data.get("players") or {}
    if isinstance(players, list):
        player_count = len(players)
    else:
        player_count = len(players.keys())

    dealt_in = data.get("dealt_in_seats") or []
    positions = data.get("positions") or {}
    actions = data.get("actions") or []
    board = data.get("board") or []
    hero_cards = data.get("hero_cards") or []

    hero_position = (
        data.get("hero_position")
        or positions.get(data.get("hero_seat"))
        or "UNKNOWN"
    )

    reached = ["PREFLOP"]
    if len(board) >= 3:
        reached.append("FLOP")
    if len(board) >= 4:
        reached.append("TURN")
    if len(board) >= 5:
        reached.append("RIVER")

    unknown_position_seats = [
        seat
        for seat in dealt_in
        if not positions.get(seat)
        or str(positions.get(seat)).upper() == "UNKNOWN"
    ]

    low_confidence_actions = [
        action
        for action in actions
        if float(action.get("confidence") or 0.0) < 0.90
    ]

    warnings = []

    if player_count == 0:
        warnings.append("No starting players were recorded.")

    if not dealt_in:
        warnings.append("Starting participant roster was not frozen.")

    if hero_position == "UNKNOWN":
        warnings.append("Hero position is unknown.")

    if unknown_position_seats:
        warnings.append(
            "Missing positions: "
            + ", ".join(unknown_position_seats)
        )

    if not Path(archived).exists():
        warnings.append("History archive was not created.")

    if not CANONICAL_STORE.text_path.exists():
        warnings.append("current_hand.txt is missing.")

    status = "PASS" if not warnings else "WARN"

    lines = [
        "=" * 52,
        "POKER INTELLIGENCE VALIDATION",
        "=" * 52,
        "",
        f"Status: {status}",
        f"Hand ID: {data.get('hand_id') or 'unknown'}",
        f"Hero: {hero_position}",
        f"Cards: {' '.join(hero_cards) if hero_cards else 'unknown'}",
        f"Board: {' '.join(board) if board else 'none'}",
        f"Result: {data.get('result') or 'unknown'}",
        "",
        "TABLE",
        "-" * 52,
        f"Seated players: {player_count}",
        f"Dealt-in players: {len(dealt_in)}",
        f"Positions assigned: {len(positions)}",
        "",
        "STREETS",
        "-" * 52,
        f"Reached: {' -> '.join(reached)}",
        "",
        "ACTIONS",
        "-" * 52,
        f"Canonical actions: {len(actions)}",
        f"Low-confidence actions: {len(low_confidence_actions)}",
        "",
        "OUTPUT",
        "-" * 52,
        f"Current hand: {CANONICAL_STORE.text_path}",
        f"Archive: {archived}",
    ]

    if warnings:
        lines.extend([
            "",
            "WARNINGS",
            "-" * 52,
        ])
        lines.extend(
            f"- {warning}"
            for warning in warnings
        )

    lines.extend([
        "",
        "=" * 52,
        "",
    ])

    VALIDATION_SUMMARY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    VALIDATION_SUMMARY_PATH.write_text(
        "\n".join(lines)
    )

    print(
        f"[VALIDATION] {status} "
        f"summary={VALIDATION_SUMMARY_PATH}",
        flush=True,
    )


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
    write_validation_summary(
        canonical,
        archived,
    )

    print(f"[ARCHIVE] {archived}")
    print("[STATE] -> COMPLETE", result)

    return default_state()


def handle_event(state, event):
    t = event.get("type")

    if t == "table_context":
        return handle_table_context(state, event)

    if t == "table_snapshot":
        return handle_table_snapshot(state, event)

    if t == "stack_update":
        return handle_stack_update(state, event)

    if t == "pot_update":
        return handle_pot_update(state, event)

    if t == "hero_cards":
        return handle_hero_cards(state, event)

    if t == "board":
        return handle_board(state, event)

    if t == "hero_decision":
        return handle_hero_decision(state, event)

    if t == "hero_action_complete":
        return handle_hero_action_complete(state, event)

    if t == "hero_fold":
        return handle_hero_fold(state, event)

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
