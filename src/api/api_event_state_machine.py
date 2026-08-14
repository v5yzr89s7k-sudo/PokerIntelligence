from pathlib import Path
import json
import time
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
CURSOR = ROOT / "runtime/live/api_event_state_machine_cursor.txt"
STATE_PATH = ROOT / "runtime/live/api_event_state_machine_state.json"
BETTING_ROUND_STATUS_PATH = (
    ROOT / "runtime/live/betting_round_status.json"
)

BOUNDARY_STACK_RESULTS_PATH = (
    ROOT / "runtime/live/boundary_stack_results.jsonl"
)
BOUNDARY_STACK_CURSOR_PATH = (
    ROOT / "runtime/live/boundary_stack_state_machine_cursor.txt"
)

from src.api.position_engine import assign_positions
from src.state.canonical_hand import CanonicalHand
from src.state.canonical_hand_store import CanonicalHandStore
from src.state.betting_round_tracker import BettingRoundTracker
from src.state.boundary_result_promoter import (
    promote_boundary_observation,
)
from src.api.participant_validation_recorder import (
    record_participant_comparison,
)


CANONICAL_STORE = CanonicalHandStore()

# One BettingRoundTracker lives for exactly one hand.
_ACTIVE_TRACKER = None
_ACTIVE_HAND_ID = None


def tracker_for_hand(canonical):
    global _ACTIVE_TRACKER
    global _ACTIVE_HAND_ID

    hand_id = canonical.hand_id or "__unknown__"

    if (
        _ACTIVE_TRACKER is None
        or _ACTIVE_HAND_ID != hand_id
    ):
        _ACTIVE_TRACKER = BettingRoundTracker(canonical)
        _ACTIVE_HAND_ID = hand_id

        print(
            f"[TRACKER] initialized hand={hand_id}",
            flush=True,
        )

    else:
        # Always point the tracker at the latest CanonicalHand
        # loaded from disk.
        _ACTIVE_TRACKER.hand = canonical

    return _ACTIVE_TRACKER


def reset_tracker():
    global _ACTIVE_TRACKER
    global _ACTIVE_HAND_ID

    _ACTIVE_TRACKER = None
    _ACTIVE_HAND_ID = None

    print("[TRACKER] reset", flush=True)


def write_betting_round_status(tracker, canonical, state=None):
    """
    Publish authoritative betting-round state for read-only downstream
    consumers.

    hand_id identifies CanonicalHand persistence. hand_token identifies the
    live perception hand. Both are published so asynchronous consumers can
    reject stale status from another live hand.
    """
    status = tracker.commitment_tracker.round_status(
        canonical.current_street
    )
    status["hand_id"] = canonical.hand_id
    status["hand_token"] = str(
        (state or {}).get("hand_token") or ""
    )
    status["canonical_players_to_act"] = list(
        canonical.players_to_act or []
    )
    status["processed_episode_count"] = len(
        tracker.processed_episode_ids
    )

    BETTING_ROUND_STATUS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    BETTING_ROUND_STATUS_PATH.write_text(
        json.dumps(status, indent=2) + "\n"
    )

    return status


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


def read_boundary_stack_cursor():
    if BOUNDARY_STACK_CURSOR_PATH.exists():
        try:
            return int(
                BOUNDARY_STACK_CURSOR_PATH
                .read_text()
                .strip()
                or "0"
            )
        except Exception:
            return 0
    return 0


def save_boundary_stack_cursor(n):
    BOUNDARY_STACK_CURSOR_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    BOUNDARY_STACK_CURSOR_PATH.write_text(
        str(int(n)) + "\n"
    )


def default_state():
    return {
        "phase": "WAITING",
        "snapshot_cached": False,
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
        "canonical_snapshot_ready": False,
        "pending_board_events": [],
        "pending_inferred_actions": [],
        "pending_stack_baseline_observations": [],
        "pending_stack_updates": [],
        "pending_pot_updates": [],
        "pending_high_pot": None,
        "pending_terminal_events": [],
        "winner_seat": None,
        "final_pot_bb": None,
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
    prior_dealt_in_seats = list(
        state.get("dealt_in_seats") or []
    )
    snapshot_dealt_in_seats = list(
        event.get("dealt_in_seats") or []
    )
    dealt_in_seats = (
        snapshot_dealt_in_seats
        or prior_dealt_in_seats
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
            local_dealt_in=prior_dealt_in_seats,
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

    dealer_button_seat = (
        event.get("dealer_button_seat")
        or state.get("dealer_button_seat")
        or ""
    )
    positions = dict(
        event.get("positions")
        or state.get("positions")
        or {}
    )
    hero_position = (
        event.get("hero_position")
        or positions.get("hero")
        or state.get("hero_position")
        or "unknown"
    )

    state["players"] = players
    state["dealt_in_seats"] = list(dealt_in_seats)
    state["dealer_button_seat"] = dealer_button_seat
    state["positions"] = positions
    state["hero_position"] = hero_position

    if event_hand_token:
        state["hand_token"] = event_hand_token

    if state.get("phase") != "WAITING":

        if state.get("canonical_snapshot_ready"):
            canonical = canonical_load()
        else:
            canonical = CanonicalHand().start_hand(
                hand_id=f"live-{int(state['hand_started_at'] * 1000)}",
                players=players,
                hero_cards=state.get("hero_cards", []),
                hero_position=hero_position,
                positions=positions,
                started_ts=state["hand_started_at"],
            )

            canonical.dealt_in_seats = list(
                dealt_in_seats
            )

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

        pending_events = []

        for pending_event in list(
            state.get(
                "pending_stack_baseline_observations"
            )
            or []
        ):
            pending_events.append(
                (
                    "stack_baseline_observation",
                    dict(pending_event),
                )
            )

        for pending_event in list(
            state.get("pending_stack_updates") or []
        ):
            pending_events.append(
                ("stack_update", dict(pending_event))
            )

        for pending_event in list(
            state.get("pending_pot_updates") or []
        ):
            pending_events.append(
                ("pot_update", dict(pending_event))
            )

        for pending_event in list(
            state.get("pending_board_events") or []
        ):
            pending_events.append(
                ("board", dict(pending_event))
            )

        for pending_event in list(
            state.get("pending_inferred_actions") or []
        ):
            pending_events.append(
                ("inferred_action", dict(pending_event))
            )

        for pending_event in list(
            state.get("pending_terminal_events") or []
        ):
            event_type = pending_event.get("type")

            if event_type in (
                "hero_fold",
                "hand_complete",
            ):
                pending_events.append(
                    (event_type, dict(pending_event))
                )

        state["pending_board_events"] = []
        state["pending_inferred_actions"] = []
        state["pending_stack_baseline_observations"] = []
        state["pending_stack_updates"] = []
        state["pending_pot_updates"] = []
        state["pending_terminal_events"] = []

        pending_events.sort(
            key=lambda item: float(
                item[1].get("ts") or 0.0
            )
        )

        for event_type, pending_event in pending_events:
            if event_type == "stack_baseline_observation":
                state = handle_stack_baseline_observation(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered "
                    "stack_baseline_observation "
                    f"{pending_event.get('seat')}",
                    flush=True,
                )

            elif event_type == "stack_update":
                state = handle_stack_update(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered stack_update "
                    f"{pending_event.get('seat')}",
                    flush=True,
                )

            elif event_type == "winner_detected":
                state = handle_winner_detected(
                    state,
                    pending_event,
                )

            elif event_type == "pot_update":
                state = handle_pot_update(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered pot_update "
                    f"{pending_event.get('pot_bb')}",
                    flush=True,
                )

            elif event_type == "board":
                state = handle_board(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered board "
                    f"{pending_event.get('board') or []}",
                    flush=True,
                )

            elif event_type == "inferred_action":
                state = handle_inferred_action(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered inferred_action "
                    f"{pending_event.get('street')} "
                    f"{pending_event.get('seat')} "
                    f"{pending_event.get('action')}",
                    flush=True,
                )

            elif event_type == "hero_fold":
                state = handle_hero_fold(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered hero_fold",
                    flush=True,
                )

            elif event_type == "hand_complete":
                state = handle_hand_complete(
                    state,
                    pending_event,
                )
                print(
                    "[STATE] replayed buffered hand_complete",
                    flush=True,
                )
                break

    print("[STATE] table_snapshot", hero_position, f"players={len(players)}")
    return state



def handle_table_context(state, event):
    """
    Temporary diagnostic event.

    The initial table snapshot is now the authoritative source for:
      - roster
      - dealt-in seats
      - dealer
      - positions
      - Hero position
      - starting stacks

    table_context remains only to support participant validation during
    the migration and will be removed after validation is complete.
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

    # Snapshot is now the authoritative source for roster,
    # positions, dealer, and dealt-in seats.
    #
    # table_context is retained temporarily for diagnostics and
    # participant validation only.
    state["participant_frame_count"] = int(
        event.get("participant_frame_count") or 0
    )
    state["participant_validation_recorded"] = False

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
    # The initial table snapshot is the authoritative source for
    # roster, positions, dealer, and starting stacks.
    state["canonical_snapshot_ready"] = False
    state["pending_board_events"] = []
    state["pending_inferred_actions"] = []
    # Preserve trusted pre-change baselines captured during the short
    # local-hand-start / canonical-hand-start race. They are already scoped
    # to the emerging hand by hand_token and will be replayed once the
    # authoritative table snapshot is available.
    state["pending_stack_baseline_observations"] = list(
        state.get("pending_stack_baseline_observations")
        or []
    )
    state["pending_stack_updates"] = []
    state["pending_pot_updates"] = []
    state["pending_terminal_events"] = []

    print(
        "[CANONICAL_INIT] deferred until table snapshot",
        flush=True,
    )

    state = record_timeline(state, f"hero_cards {' '.join(cards)}")
    print("[STATE] WAITING -> PREFLOP", cards)

    return state


def handle_stack_baseline_observation(state, event):
    """
    Promote independently observed pre-change stack pixels into an unresolved
    canonical starting baseline.

    The coordinator supplies perception evidence only. CanonicalHand remains
    the sole owner of authoritative stack state.
    """
    if state.get("phase") == "WAITING":
        # A local hand-start token may already exist before Hero-card API
        # confirmation moves canonical state to PREFLOP. Trusted pre-change
        # stack evidence from that short race belongs to the emerging hand
        # and must survive into the existing snapshot buffer.
        #
        # Ordinary between-hand WAITING observations remain rejected.
        if not state.get("hand_token"):
            print(
                "[SKIP] stack_baseline_observation while waiting",
                flush=True,
            )
            return state

        print(
            "[BUFFER_ELIGIBLE] stack_baseline_observation "
            "during emerging-hand WAITING "
            f"seat={event.get('seat')}",
            flush=True,
        )

    seat = event.get("seat")
    observed_stack_bb = event.get("observed_stack_bb")

    if not seat or observed_stack_bb is None:
        print(
            "[SKIP] invalid stack_baseline_observation",
            event,
            flush=True,
        )
        return state

    confidence = float(
        event.get("confidence") or 0.0
    )
    votes = int(
        event.get("votes") or 0
    )

    # This event is allowed to initialize canonical stack state only from the
    # independently segmented pre-change family. Keep the existing strong
    # perception threshold.
    if confidence < 0.95 or votes < 3:
        print(
            "[STACK_BASELINE_REJECT] "
            f"seat={seat} "
            f"confidence={confidence:.2f} "
            f"votes={votes} "
            "reason=untrusted_prechange_observation",
            flush=True,
        )
        return state

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get(
                "pending_stack_baseline_observations"
            )
            or []
        )

        pending.append(dict(event))
        pending.sort(
            key=lambda item: float(
                item.get("ts") or 0.0
            )
        )

        state[
            "pending_stack_baseline_observations"
        ] = pending

        print(
            "[BUFFER] stack_baseline_observation "
            f"until table_snapshot seat={seat}",
            flush=True,
        )

        return state

    canonical = canonical_load()

    result = canonical.resolve_starting_stack_baseline(
        seat=seat,
        observed_stack_bb=float(observed_stack_bb),
    )

    if result is None:
        print(
            "[STACK_BASELINE_REJECT] "
            f"seat={seat} reason=unknown_seat",
            flush=True,
        )
        return state

    if not result.get("resolved"):
        print(
            "[STACK_BASELINE_REJECT] "
            f"seat={seat} "
            f"observed={float(observed_stack_bb):.2f} "
            f"reason={result.get('reason')}",
            flush=True,
        )
        return state

    canonical_save(canonical)

    print(
        "[CANONICAL_STACK_BASELINE] "
        f"seat={seat} "
        f"stack={float(result['starting_stack_bb']):.2f} "
        f"confidence={confidence:.2f} "
        f"votes={votes} "
        "source=prechange_stack_pixels",
        flush=True,
    )

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

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get("pending_stack_updates") or []
        )
        pending.append(dict(event))
        pending.sort(
            key=lambda item: float(item.get("ts") or 0.0)
        )
        state["pending_stack_updates"] = pending

        print(
            f"[BUFFER] stack_update until table_snapshot "
            f"seat={seat}",
            flush=True,
        )
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


def handle_winner_detected(state, event):
    """
    Preserve the canonical winning seat at the visual terminal boundary.

    WINNER detection is result evidence only here. Coordinator-side action
    ownership freezing is handled separately.
    """
    if state.get("phase") == "WAITING":
        print(
            "[SKIP] winner_detected while waiting",
            flush=True,
        )
        return state

    seat = str(
        event.get("seat") or ""
    ).strip()

    if not seat:
        print(
            "[SKIP] winner_detected without seat",
            flush=True,
        )
        return state

    players = state.get("players") or []

    known_seats = {
        str(player.get("seat") or "")
        for player in players
        if player.get("seat")
    }

    # Once the authoritative snapshot exists, do not allow an arbitrary
    # detector label to become canonical result ownership.
    if (
        state.get("canonical_snapshot_ready")
        and known_seats
        and seat not in known_seats
    ):
        print(
            "[WINNER_REJECT] "
            f"seat={seat} "
            "reason=seat_not_in_canonical_snapshot",
            flush=True,
        )
        return state

    existing = state.get("winner_seat")

    if existing and existing != seat:
        print(
            "[WINNER_REJECT] "
            f"existing={existing} "
            f"observed={seat} "
            "reason=winner_conflict",
            flush=True,
        )
        return state

    state["winner_seat"] = seat

    print(
        "[WINNER_DETECTED] "
        f"seat={seat} "
        f"confidence={float(event.get('confidence') or 0.0):.2f}",
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

        # A terminal pot observation is requested specifically to settle the
        # completed hand. It is not an ordinary in-street estimate and must
        # not be held behind expected-pot/high-spike confirmation.
        if event.get("terminal"):
            canonical = canonical_load()

            accepted = canonical.set_observed_pot(
                observed
            )

            canonical_save(canonical)

            state["final_pot_bb"] = round(
                float(accepted),
                2,
            )
            state["pending_high_pot"] = None

            print(
                "[CANONICAL_TERMINAL_POT] "
                f"accepted={float(accepted):.2f} "
                "source=terminal_table_pot",
                flush=True,
            )

            return state
    except (TypeError, ValueError):
        print("[SKIP] invalid pot_update", event)
        return state

    if not 0.1 <= observed <= 1000.0:
        print(f"[SKIP] out-of-range pot_update pot={observed}")
        return state

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get("pending_pot_updates") or []
        )
        pending.append(dict(event))
        pending.sort(
            key=lambda item: float(item.get("ts") or 0.0)
        )
        state["pending_pot_updates"] = pending

        print(
            f"[BUFFER] pot_update until table_snapshot "
            f"pot={observed:.2f}",
            flush=True,
        )
        return state

    canonical = canonical_load()
    expected = canonical.expected_pot_bb

    # A validated table-pot observation is authoritative. The reconstructed
    # expected pot is derived from inferred actions and may be incomplete.
    # Keep the expected value for diagnostics and fallback only; never use it
    # to reject an otherwise valid observed pot.
    if expected is None:
        expected_text = "unknown"
        difference_text = "unknown"
    else:
        expected = round(float(expected), 2)
        difference = round(observed - expected, 2)
        expected_text = f"{expected:.2f}"
        difference_text = f"{difference:.2f}"

    if expected is not None:
        tolerance = max(
            1.0,
            round(expected * 0.35, 2),
        )

        lower_bound = expected - tolerance
        upper_bound = expected + tolerance

        # An observed pot materially below already reconstructed
        # commitments contradicts canonical accounting.
        if observed < lower_bound:
            state["pending_high_pot"] = None

            print(
                "[CANONICAL_POT_REJECT]",
                f"observed={observed:.2f}",
                f"expected={expected:.2f}",
                f"difference={observed - expected:.2f}",
                f"tolerance={tolerance:.2f}",
                "reason=below_canonical_commitments",
                flush=True,
            )

            return state

        # A much higher table pot can be legitimate when action inference
        # missed calls, raises, or all-in commitments. However, one isolated
        # OCR spike must not overwrite canonical state.
        #
        # Require a second high observation on the SAME street before
        # promoting the larger observed pot to authoritative state.
        if observed > upper_bound:
            pending_high = state.get("pending_high_pot") or {}
            pending_phase = pending_high.get("phase")
            pending_value = pending_high.get("pot_bb")

            confirmed_high = bool(
                pending_phase == state.get("phase")
                and pending_value is not None
                and observed >= float(pending_value) - 1.0
            )

            if not confirmed_high:
                state["pending_high_pot"] = {
                    "phase": state.get("phase"),
                    "pot_bb": observed,
                    "ts": event.get("ts") or time.time(),
                }

                print(
                    "[CANONICAL_POT_PENDING_HIGH]",
                    f"observed={observed:.2f}",
                    f"expected={expected:.2f}",
                    f"difference={observed - expected:.2f}",
                    f"phase={state.get('phase')}",
                    "reason=awaiting_same_street_confirmation",
                    flush=True,
                )

                return state

            print(
                "[CANONICAL_POT_CONFIRMED_HIGH]",
                f"previous={float(pending_value):.2f}",
                f"observed={observed:.2f}",
                f"expected={expected:.2f}",
                f"phase={state.get('phase')}",
                flush=True,
            )

        state["pending_high_pot"] = None

    accepted = canonical.set_observed_pot(observed)
    canonical_save(canonical)

    print(
        f"[CANONICAL_POT] accepted={accepted:.2f} "
        f"expected={expected_text} "
        f"difference={difference_text} "
        "source=observed_table_pot",
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
    state["pending_high_pot"] = None

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

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get("pending_terminal_events") or []
        )
        pending.append({
            **dict(event),
            "type": "hero_fold",
        })
        pending.sort(
            key=lambda item: float(item.get("ts") or 0.0)
        )
        state["pending_terminal_events"] = pending

        print(
            "[BUFFER] hero_fold until table_snapshot",
            flush=True,
        )
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

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get("pending_inferred_actions") or []
        )
        pending.append(dict(event))
        pending.sort(
            key=lambda item: float(item.get("ts") or 0.0)
        )
        state["pending_inferred_actions"] = pending

        print(
            "[BUFFER] inferred_action until table_snapshot "
            f"street={event.get('street')} "
            f"seat={event.get('seat')} "
            f"action={event.get('action')}",
            flush=True,
        )
        return state

    canonical = canonical_load()

    seat = event.get("seat")
    player = canonical.players.get(seat)

    if (
        player is not None
        and (
            player.folded
            or not player.active
        )
    ):
        print(
            f"[CANONICAL_SKIP] "
            f"{event.get('street')} "
            f"{seat} "
            f"{event.get('action')} "
            "reason=player_already_folded_or_inactive",
            flush=True,
        )
        return state

    tracker = tracker_for_hand(canonical)
    added = tracker.ingest(event)

    status = write_betting_round_status(
        tracker,
        canonical,
        state,
    )

    print(
        f"[BETTING_STATUS] street={status['street']} "
        f"complete={status['complete']} "
        f"owing={status['players_owing_action']}",
        flush=True,
    )

    decision = tracker.decisions[-1] if tracker.decisions else None

    if added is None:
        if decision is not None:
            print(
                f"[CANONICAL_SKIP] {event.get('street')} "
                f"{event.get('seat')} {event.get('action')} "
                f"reason={decision.reason}"
            )

            # Deferred actions remain pending for replay.
            if "deferred" in decision.reason.lower():
                pending = list(
                    state.get("pending_inferred_actions") or []
                )

                pending.append(dict(event))
                pending.sort(
                    key=lambda item: float(item.get("ts") or 0.0)
                )

                state["pending_inferred_actions"] = pending

                print(
                    "[BUFFER] deferred inferred_action "
                    f"seat={event.get('seat')} "
                    f"action={event.get('action')}",
                    flush=True,
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

    pending = list(
        state.get("pending_inferred_actions") or []
    )

    if pending:
        state["pending_inferred_actions"] = []

        pending.sort(
            key=lambda item: float(
                item.get("ts") or 0.0
            )
        )

        print(
            f"[REPLAY] retrying {len(pending)} deferred inferred actions",
            flush=True,
        )

        for pending_event in pending:
            state = handle_inferred_action(
                state,
                pending_event,
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

    if not state.get("canonical_snapshot_ready"):
        pending = list(
            state.get("pending_terminal_events") or []
        )
        pending.append({
            **dict(event),
            "type": "hand_complete",
        })
        pending.sort(
            key=lambda item: float(item.get("ts") or 0.0)
        )
        state["pending_terminal_events"] = pending

        print(
            "[BUFFER] hand_complete until table_snapshot",
            flush=True,
        )
        return state

    result = event.get("result") or "Hand complete"
    state["phase"] = "COMPLETE"
    state["snapshot_cached"] = False
    state["hand_complete"] = True
    state["result"] = result

    state = record_timeline(state, f"hand_complete {result}")
    canonical = canonical_load()

    winner_seat = state.get("winner_seat")
    final_pot_bb = state.get("final_pot_bb")

    # Structured terminal result must be attached before finish/archive.
    # CanonicalHand already owns the pot-result representation.
    if (
        winner_seat
        or final_pot_bb is not None
    ):
        canonical.add_pot_result(
            pot_type="final_pot",
            amount_bb=(
                float(final_pot_bb)
                if final_pot_bb is not None
                else None
            ),
            winners=(
                [winner_seat]
                if winner_seat
                else []
            ),
        )

        print(
            "[CANONICAL_FINAL_RESULT] "
            f"winner={winner_seat or 'unknown'} "
            f"pot={final_pot_bb}",
            flush=True,
        )

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

    reset_tracker()

    if BETTING_ROUND_STATUS_PATH.exists():
        BETTING_ROUND_STATUS_PATH.unlink()

    return default_state()


def handle_boundary_stack_result(state, result):
    """
    Consume one asynchronous retrospective stack result.

    The result stream carries objective perception evidence only.
    Poker semantics are resolved here against the state-machine-owned
    preserved betting obligations for the street that just ended.
    """
    if state.get("phase") == "WAITING":
        print(
            "[BOUNDARY_RESULT_SKIP] reason=waiting",
            flush=True,
        )
        return state

    if not state.get("canonical_snapshot_ready"):
        print(
            "[BOUNDARY_RESULT_SKIP] "
            "reason=canonical_snapshot_not_ready",
            flush=True,
        )
        return state

    result_token = str(
        result.get("hand_token") or ""
    )
    state_token = str(
        state.get("hand_token") or ""
    )

    if (
        not result_token
        or not state_token
        or result_token != state_token
    ):
        print(
            "[BOUNDARY_RESULT_SKIP] "
            "reason=hand_token_mismatch "
            f"state={state_token[:8]} "
            f"result={result_token[:8]}",
            flush=True,
        )
        return state

    old_street = str(
        result.get("street") or ""
    ).upper()

    current_street = str(
        state.get("phase") or ""
    ).upper()

    expected_current = {
        "PREFLOP": "FLOP",
        "FLOP": "TURN",
        "TURN": "RIVER",
    }.get(old_street)

    if expected_current != current_street:
        print(
            "[BOUNDARY_RESULT_SKIP] "
            "reason=street_relationship_mismatch "
            f"old={old_street} "
            f"current={current_street}",
            flush=True,
        )
        return state

    canonical = canonical_load()
    tracker = tracker_for_hand(canonical)

    observations = list(
        result.get("observations") or []
    )

    # Worker/request order is transport order, not poker chronology.
    #
    # Promote terminal observations in the preserved old-street response
    # order owned by StreetCommitmentTracker. Any extra/non-owing result
    # remains harmless and is processed afterward, where the promoter's
    # obligation gate will reject it.
    observation_by_seat = {
        str(item.get("seat") or ""): item
        for item in observations
        if isinstance(item, dict)
        and item.get("seat")
    }

    preserved_owing_order = list(
        tracker.commitment_tracker
        .players_owing_action(old_street)
    )

    ordered_seats = list(
        dict.fromkeys(
            preserved_owing_order
            + list(observation_by_seat)
        )
    )

    promoted = []

    for seat in ordered_seats:
        item = observation_by_seat.get(seat)

        if not isinstance(item, dict):
            continue

        observation = item.get("observation")

        if not isinstance(observation, dict):
            continue

        promotion = promote_boundary_observation(
            hand=canonical,
            commitment_tracker=(
                tracker.commitment_tracker
            ),
            street=old_street,
            seat=seat,
            observation=observation,
        )

        if promotion.resolved:
            promoted.append(
                promotion.to_dict()
            )

            state = record_timeline(
                state,
                "boundary_action "
                f"{old_street} "
                f"{seat} "
                f"{promotion.action}",
            )

            print(
                "[BOUNDARY_ACTION] "
                f"street={old_street} "
                f"seat={seat} "
                f"action={promotion.action} "
                f"sequence={promotion.canonical_sequence}",
                flush=True,
            )
        else:
            print(
                "[BOUNDARY_UNRESOLVED] "
                f"street={old_street} "
                f"seat={seat} "
                f"reason={promotion.reason}",
                flush=True,
            )

    if promoted:
        canonical_save(canonical)

    old_status = (
        tracker.commitment_tracker.round_status(
            old_street
        )
    )

    print(
        "[BOUNDARY_STATUS] "
        f"street={old_street} "
        f"complete={old_status.get('complete')} "
        f"owing={old_status.get('players_owing_action')}",
        flush=True,
    )

    # Keep the public status artifact current-street scoped.
    write_betting_round_status(
        tracker,
        canonical,
        state,
    )

    return state


def handle_event(state, event):
    t = event.get("type")

    if t == "table_context":
        return handle_table_context(state, event)

    if t == "table_snapshot":
        return handle_table_snapshot(state, event)

    if t == "stack_baseline_observation":
        return handle_stack_baseline_observation(
            state,
            event,
        )

    if t == "stack_update":
        return handle_stack_update(state, event)

    if t == "boundary_stack_result":
        return handle_boundary_stack_result(
            state,
            event,
        )

    if t == "winner_detected":
        return handle_winner_detected(
            state,
            event,
        )

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

        # Boundary OCR is intentionally outside api_events.jsonl.
        # Consume its result stream against the same in-memory tracker
        # that owns preserved old-street betting obligations.
        if BOUNDARY_STACK_RESULTS_PATH.exists():
            boundary_lines = (
                BOUNDARY_STACK_RESULTS_PATH
                .read_text()
                .splitlines()
            )
            boundary_cursor = (
                read_boundary_stack_cursor()
            )

            for i in range(
                boundary_cursor,
                len(boundary_lines),
            ):
                line = boundary_lines[i].strip()

                if not line:
                    save_boundary_stack_cursor(i + 1)
                    continue

                try:
                    result = json.loads(line)
                except Exception:
                    # A worker may be in the middle of appending.
                    # Do not advance the cursor past a partial line.
                    break

                if (
                    result.get("type")
                    != "boundary_stack_result"
                ):
                    save_boundary_stack_cursor(i + 1)
                    continue

                state = handle_boundary_stack_result(
                    state,
                    result,
                )
                save_state(state)
                save_boundary_stack_cursor(i + 1)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
