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
from src.state.preserved_action_reconciler import (
    reconcile_preserved_actions,
)

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

        # CanonicalHand may have advanced streets even when no inferred
        # player action occurred on the new street. Keep the persistent
        # betting tracker synchronized so the new street's action
        # obligations remain authoritative for boundary reconciliation.
        _ACTIVE_TRACKER._sync_street()

    return _ACTIVE_TRACKER


def reset_tracker():
    global _ACTIVE_TRACKER
    global _ACTIVE_HAND_ID

    _ACTIVE_TRACKER = None
    _ACTIVE_HAND_ID = None

    print("[TRACKER] reset", flush=True)


def write_betting_round_status(
    tracker,
    canonical,
    state=None,
    *,
    processed_event_cursor=None,
):
    """
    Publish authoritative betting-round state for read-only downstream
    consumers.

    hand_id identifies CanonicalHand persistence. hand_token identifies the
    live perception hand. Both are published so asynchronous consumers can
    reject stale status from another live hand.

    processed_event_cursor is the next-unprocessed api_events.jsonl index.
    A published value N guarantees that every event at index < N completed
    its full state-machine transaction before this status was published.

    Handler-internal writes do not advance that acknowledgement. They preserve
    the last proven cursor until the main event loop explicitly advances it.
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

    current_street = str(
        canonical.current_street
        or ""
    ).upper()

    unresolved_candidates = {
        str(item.get("seat") or "")
        for item in (
            (state or {}).get(
                "unresolved_stack_candidates"
            )
            or {}
        ).values()
        if (
            isinstance(item, dict)
            and str(
                item.get("street")
                or ""
            ).upper()
            == current_street
            and item.get("seat")
        )
    }

    provisional_bets = {
        str(item.get("seat") or "")
        for item in (
            (state or {}).get(
                "unresolved_provisional_bets"
            )
            or {}
        ).values()
        if (
            isinstance(item, dict)
            and str(
                item.get("street")
                or ""
            ).upper()
            == current_street
            and item.get("seat")
        )
    }

    # Reuse the exact ownership helper already used by board
    # promotion rather than inventing a second interpretation
    # of physical commitment state.
    ownership = (
        unresolved_board_ownership(
            state,
            street=current_street,
        )
    )

    commitment_candidates = set(
        ownership.get(
            "commitment_candidates"
        )
        or []
    )

    status[
        "boundary_can_skip_stack_ocr"
    ] = (
        boundary_can_resolve_passively_without_stack_ocr(
            street=current_street,
            betting_open=bool(
                status.get("betting_open")
            ),
            current_price=status.get(
                "current_price"
            ),
            last_aggressor=status.get(
                "last_aggressor"
            ),
            unresolved_candidates=(
                unresolved_candidates
            ),
            provisional_bets=(
                provisional_bets
            ),
            commitment_candidates=(
                commitment_candidates
            ),
        )
    )

    status[
        "boundary_skip_stack_ocr_context"
    ] = {
        "street": current_street,
        "unresolved_candidates": sorted(
            unresolved_candidates
        ),
        "provisional_bets": sorted(
            provisional_bets
        ),
        "commitment_candidates": sorted(
            commitment_candidates
        ),
    }
    status["processed_episode_count"] = len(
        tracker.processed_episode_ids
    )

    if processed_event_cursor is None:
        previous_cursor = None

        if BETTING_ROUND_STATUS_PATH.exists():
            try:
                previous_status = json.loads(
                    BETTING_ROUND_STATUS_PATH.read_text()
                )

                previous_cursor = (
                    previous_status.get(
                        "processed_event_cursor"
                    )
                    if isinstance(previous_status, dict)
                    else None
                )
            except Exception:
                previous_cursor = None

        if previous_cursor is not None:
            status["processed_event_cursor"] = int(
                previous_cursor
            )

    else:
        status["processed_event_cursor"] = int(
            processed_event_cursor
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


def refresh_live_presentation(state):
    if not state.get("canonical_snapshot_ready"):
        return state

    canonical = canonical_load()

    presentation = {}

    # ------------------------------------------------------------
    # Earliest physical commitment presentation
    # ------------------------------------------------------------
    #
    # These entries exist only for current_hand.txt latency.
    # They carry no quantitative or betting-accounting authority.
    live_commitments = dict(
        state.get("pending_live_commitments")
        or {}
    )

    for key, item in list(
        live_commitments.items()
    ):
        if not isinstance(item, dict):
            live_commitments.pop(
                key,
                None,
            )
            continue

        street = str(
            item.get("street") or ""
        ).upper()

        seat = str(
            item.get("seat") or ""
        )

        if (
            street not in {"PREFLOP", "FLOP", "TURN", "RIVER"}
            or not seat
        ):
            live_commitments.pop(
                key,
                None,
            )
            continue

        # Canonical settlement owns presentation immediately.
        # Remove stale physical-only overlay ownership.
        canonical_owner_exists = any(
            action.street == street
            and action.seat == seat
            and action.action.upper()
            not in {
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
            for action in canonical.actions
        )

        if canonical_owner_exists:
            live_commitments.pop(
                key,
                None,
            )
            continue

        presentation_action = str(
            item.get("action")
            or (
                "BET_OR_RAISE"
                if street == "PREFLOP"
                else "BET"
            )
        ).upper()

        presentation[
            f"{street}:{seat}"
        ] = {
            "seat": seat,
            "street": street,
            "action": presentation_action,
            "ts": item.get("ts"),
        }

    state[
        "pending_live_commitments"
    ] = live_commitments

    # ------------------------------------------------------------
    # Existing Stage-1 quantitative provisional lifecycle
    # ------------------------------------------------------------
    for item in (
        state.get("unresolved_provisional_bets")
        or {}
    ).values():
        if not isinstance(item, dict):
            continue

        street = str(
            item.get("street") or ""
        ).upper()

        seat = str(
            item.get("seat") or ""
        )

        if (
            street not in {"FLOP", "TURN", "RIVER"}
            or not seat
        ):
            continue

        # Stage 1/2 expose only an unsized opening BET.
        # Once canonical aggression already exists, CALL versus
        # RAISE semantics may be unresolved and must not be guessed.
        existing_aggression = any(
            action.street == street
            and action.action.upper()
            in {"BET", "RAISE", "BET_OR_RAISE"}
            for action in canonical.actions
        )

        if existing_aggression:
            continue

        # Canonical action for this exact seat/street always wins.
        if any(
            action.street == street
            and action.seat == seat
            for action in canonical.actions
        ):
            continue

        presentation.setdefault(
            f"{street}:{seat}",
            {
                "seat": seat,
                "street": street,
                "action": "BET",
                "ts": item.get("ts"),
            },
        )

    provisional = list(
        presentation.values()
    )

    provisional.sort(
        key=lambda item: float(
            item.get("ts") or 0.0
        )
    )

    CANONICAL_STORE.save_live_presentation(
        canonical,
        provisional_actions=provisional,
    )

    return state


def record_physical_live_commitment(
    state,
    event,
):
    """
    Record presentation-only opening-bet evidence from the fastest
    trustworthy physical signal.

    This must never mutate CanonicalHand, pot accounting, stack accounting,
    betting price, response queues, or quantitative commitment ownership.
    """
    if not event.get("commitment_visible"):
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={event.get('street')} "
            f"seat={event.get('seat')} "
            "reason=commitment_not_visible",
            flush=True,
        )
        return state

    if (
        str(event.get("source") or "")
        != "bet_region_appeared"
    ):
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={event.get('street')} "
            f"seat={event.get('seat')} "
            "reason=source_not_commitment_appearance",
            flush=True,
        )
        return state

    if not state.get("canonical_snapshot_ready"):
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={event.get('street')} "
            f"seat={event.get('seat')} "
            "reason=canonical_snapshot_not_ready",
            flush=True,
        )
        return state

    street = str(
        event.get("street")
        or state.get("phase")
        or ""
    ).upper()

    seat = str(
        event.get("seat")
        or ""
    )

    if (
        street not in {"PREFLOP", "FLOP", "TURN", "RIVER"}
        or not seat
    ):
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={street} "
            f"seat={seat} "
            "reason=street_or_seat_not_eligible",
            flush=True,
        )
        return state

    canonical = canonical_load()

    if (
        str(canonical.current_street or "").upper()
        != street
    ):
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={street} "
            f"seat={seat} "
            f"canonical={canonical.current_street} "
            "reason=canonical_street_mismatch",
            flush=True,
        )
        return state

    if seat not in canonical.players:
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={street} "
            f"seat={seat} "
            "reason=unknown_seat",
            flush=True,
        )
        return state

    # The actor-observed chronology transaction has already run.
    # The commitment seat must now be the legitimate head actor.
    queue = list(
        canonical.players_to_act
        or []
    )

    if not queue or queue[0] != seat:
        print(
            "[LIVE_COMMITMENT_SKIP] "
            f"street={street} "
            f"seat={seat} "
            f"queue_head={queue[0] if queue else None} "
            "reason=not_head_actor",
            flush=True,
        )
        return state

    # Only an unopened postflop street is semantically safe to
    # display as BET without sizing. Facing existing aggression,
    # commitment could still resolve as CALL or RAISE.
    existing_aggression = any(
        action.street == street
        and action.action.upper()
        in {"BET", "RAISE", "BET_OR_RAISE"}
        for action in canonical.actions
    )

    if existing_aggression:
        presentation_action = "CALL_OR_RAISE"
    elif street == "PREFLOP":
        presentation_action = "BET_OR_RAISE"
    else:
        presentation_action = "BET"

    # Existing voluntary canonical action supersedes presentation
    # ownership. Forced blind posts do not: a blind may still make a
    # later voluntary commitment on PREFLOP.
    if any(
        action.street == street
        and action.seat == seat
        and action.action.upper()
        not in {
            "POST_SMALL_BLIND",
            "POST_BIG_BLIND",
        }
        for action in canonical.actions
    ):
        return state

    pending = dict(
        state.get("pending_live_commitments")
        or {}
    )

    key = f"{street}:{seat}"

    pending[key] = {
        "seat": seat,
        "street": street,
        "action": presentation_action,
        "source": "bet_region_appeared",
        "ts": event.get("ts")
        or time.time(),
    }

    state[
        "pending_live_commitments"
    ] = pending

    print(
        "[LIVE_COMMITMENT_PRESENTED] "
        f"street={street} "
        f"seat={seat} "
        f"action={presentation_action} "
        "source=bet_region_appeared",
        flush=True,
    )

    return refresh_live_presentation(
        state
    )


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
        # Physical actor observations that were chronologically valid but
        # temporarily blocked by unresolved same-street commitment evidence.
        # Preserve them until the blocking evidence settles.
        "pending_actor_observations": [],
        "pending_physical_actor_completions": [],
        "pending_stack_baseline_observations": [],
        "pending_stack_updates": [],
        "unresolved_stack_candidates": {},
        "unresolved_provisional_bets": {},
        # Durable same-hand commitment identities whose quantitative action
        # has already been accepted into canonical chronology. Asynchronous
        # bet-sizing results may arrive later, but they must never recreate
        # provisional ownership for an already-consumed commitment.
        "consumed_quantitative_commitments": {},
        "pending_pot_updates": [],
        "pending_high_pot": None,
        "pending_terminal_events": [],
        "pending_boundary_results": [],
        # Durable evidence for an ended street that is not yet semantically
        # complete. Unlike pending_boundary_results, this survives the first
        # eligible boundary replay so later deferred inferred actions can be
        # reconciled against the same retrospective observations.
        "preserved_boundary_evidence": {},
        # Qualified inferred actions whose street has already ended. These
        # are never sent through normal current-street ingestion again.
        # They are consumed only by preserved-street reconciliation.
        "preserved_inferred_actions": {},
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

    # Freeze the exact canonical forced-contribution baseline for the
    # asynchronous initial table-pot observation. Later betting actions
    # must not change the comparison baseline for that request.
    state["forced_pot_baseline_bb"] = round(
        forced_pot_bb,
        6,
    )

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
    # Structural hand topology is immutable once fast local table_context
    # has established it. The asynchronous table snapshot is enrichment and
    # validation only; it may never shrink or replace the starting roster.
    dealt_in_seats = (
        prior_dealt_in_seats
        or snapshot_dealt_in_seats
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

    # Preserve local structural truth when table_context already ran.
    # Snapshot values remain the fallback for the legacy snapshot-first path.
    prior_positions = dict(state.get("positions") or {})
    prior_dealer = state.get("dealer_button_seat") or ""
    prior_hero_position = state.get("hero_position") or ""

    local_structure_ready = bool(
        prior_dealt_in_seats
        and prior_positions
    )

    if local_structure_ready:
        dealer_button_seat = prior_dealer
        positions = prior_positions
        hero_position = (
            prior_hero_position
            or positions.get("hero")
            or "unknown"
        )
    else:
        dealer_button_seat = (
            event.get("dealer_button_seat")
            or prior_dealer
            or ""
        )
        positions = dict(
            event.get("positions")
            or prior_positions
            or {}
        )
        hero_position = (
            event.get("hero_position")
            or positions.get("hero")
            or prior_hero_position
            or "unknown"
        )

    # Merge snapshot enrichment by immutable physical seat. A missing
    # snapshot seat must retain the local bootstrap player instead of
    # disappearing from the hand.
    prior_players_by_seat = {
        item.get("seat"): dict(item)
        for item in (state.get("players") or [])
        if isinstance(item, dict) and item.get("seat")
    }
    snapshot_players_by_seat = {
        item.get("seat"): dict(item)
        for item in players
        if isinstance(item, dict) and item.get("seat")
    }

    merged_players = []

    for seat in dealt_in_seats:
        prior_player = dict(
            prior_players_by_seat.get(seat) or {}
        )
        snapshot_player = dict(
            snapshot_players_by_seat.get(seat) or {}
        )

        merged = dict(prior_player)

        for key, value in snapshot_player.items():
            # Blank asynchronous fields are not enrichment.
            if value is None or value == "":
                continue
            merged[key] = value

        merged["seat"] = seat
        merged.setdefault("is_hero", seat == "hero")
        merged.setdefault("is_active", True)

        # Never convert an unresolved physical seat into a player identity.
        # Snapshot enrichment is keyed by immutable physical seat, so a blank
        # name remains blank rather than borrowing or fabricating identity.
        merged["name"] = str(
            merged.get("name") or ""
        ).strip()

        merged_players.append(merged)

    players = merged_players

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

        # If the asynchronous snapshot is the first usable structural
        # context, retain the legacy initialization fallback. Normally the
        # local table_context has already initialized canonical state.
        #
        # CRITICAL: never rewind an already-live FLOP/TURN/RIVER hand to
        # PREFLOP merely because snapshot enrichment arrived late.
        if not state.get("canonical_snapshot_ready"):
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
    Fast local canonical bootstrap.

    table_context is produced from local perception immediately after
    Hero-card recognition. It supplies the frozen dealt-in roster, dealer,
    positions, Hero position, and best available local stack observations.

    This event MUST NOT wait for the asynchronous table snapshot. The
    snapshot is enrichment/validation only. Once table_context has enough
    structural poker information, CanonicalHand becomes live immediately so
    qualified player actions can reach current_hand.txt without API latency.
    """
    dealt_in_seats = list(event.get("dealt_in_seats") or [])
    positions = dict(event.get("positions") or {})
    dealer_button_seat = event.get("dealer_button_seat") or ""
    hero_position = (
        event.get("hero_position")
        or positions.get("hero")
        or "unknown"
    )
    hand_token = str(event.get("hand_token") or "")

    if not dealt_in_seats:
        print(
            "[TABLE_CONTEXT_DEFER] reason=no_dealt_in_seats",
            flush=True,
        )
        return state

    if state.get("phase") == "WAITING":
        print(
            "[TABLE_CONTEXT_DEFER] reason=canonical_hand_not_active",
            flush=True,
        )
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

        # Fast bootstrap publishes stack state immediately when local
        # perception has already produced a trusted numeric observation.
        #
        # Ambiguous local OCR remains provisional and is preserved only as
        # candidate evidence. It must still pass the existing independent
        # pre-change baseline resolver before becoming canonical.
        local_stack = local.get("stack_bb")

        try:
            local_confidence = float(
                local.get("stack_confidence") or 0.0
            )
        except (TypeError, ValueError):
            local_confidence = 0.0

        trusted_local_stack = (
            local_stack is not None
            and local_confidence >= 0.95
        )

        stack_candidates = list(
            local.get("stack_candidates") or []
        )

        if (
            local_stack is not None
            and local_stack not in stack_candidates
        ):
            stack_candidates.append(local_stack)

        players.append({
            "seat": seat,
            # Physical geometry is not player identity. table_context owns
            # topology and fast local stack evidence only. An unresolved name
            # remains blank until same-seat snapshot identity enrichment
            # arrives.
            "name": str(local.get("name") or "").strip(),
            "stack_bb": (
                float(local_stack)
                if trusted_local_stack
                else None
            ),
            "stack_text": (
                f"{float(local_stack):g} BB"
                if trusted_local_stack
                else ""
            ),
            "stack_candidates": stack_candidates,
            "stack_confidence": local.get("stack_confidence"),
            "stack_read_mode": (
                local.get("stack_read_mode") or "unknown"
            ),
            "is_hero": seat == "hero",
            "is_active": True,
        })

    state["players"] = players
    state["dealt_in_seats"] = list(dealt_in_seats)
    state["dealer_button_seat"] = dealer_button_seat
    state["positions"] = positions
    state["hero_position"] = hero_position
    state["participant_frame_count"] = int(
        event.get("participant_frame_count") or 0
    )
    state["participant_validation_recorded"] = False

    if hand_token:
        state["hand_token"] = hand_token

    # table_snapshot may win the startup race and initialize CanonicalHand
    # before the stronger local table_context arrives. In that ordering,
    # canonical_snapshot_ready is already True, so the normal fast-bootstrap
    # branch below will not run.
    #
    # Reconcile structural topology here. A larger local hand-start roster
    # may promote the existing canonical table, but it may never shrink it.
    if state.get("canonical_snapshot_ready"):
        canonical = canonical_load()

        canonical_seats = list(
            canonical.dealt_in_seats
            or canonical.players.keys()
        )

        canonical_seat_set = set(canonical_seats)
        local_seat_set = set(dealt_in_seats)

        structural_promotion = bool(
            local_seat_set
            and canonical_seat_set.issubset(local_seat_set)
            and local_seat_set != canonical_seat_set
        )

        if structural_promotion:
            existing_by_seat = {
                seat: player
                for seat, player in canonical.players.items()
            }

            promoted_players = []

            for player_item in players:
                seat = player_item.get("seat")

                if not seat:
                    continue

                existing = existing_by_seat.get(seat)

                item = dict(player_item)

                # The asynchronous snapshot may already have better name/stack
                # enrichment for seats it successfully recognized. Preserve
                # that evidence while adopting the local seven-seat topology.
                if existing is not None:
                    item["name"] = str(
                        existing.name
                        or item.get("name")
                        or ""
                    ).strip()

                    if existing.starting_stack_bb is not None:
                        item["stack_bb"] = (
                            existing.starting_stack_bb
                        )

                    existing_candidates = list(
                        existing.starting_stack_candidates
                        or []
                    )

                    if existing_candidates:
                        item["stack_candidates"] = (
                            existing_candidates
                        )

                    item["is_active"] = existing.active

                promoted_players.append(item)

            canonical.update_table_snapshot(
                players=promoted_players,
                hero_position=hero_position,
                positions=positions,
                dealt_in_seats=dealt_in_seats,
            )

            canonical_save(canonical)

            # The persistent betting tracker may have been initialized against
            # the smaller snapshot roster. Force it to rebuild from the
            # promoted canonical topology before voluntary action begins.
            reset_tracker()

            print(
                "[CANONICAL_STRUCTURE_PROMOTION] "
                f"players={len(canonical_seats)}"
                f"->{len(dealt_in_seats)} "
                f"added={sorted(local_seat_set - canonical_seat_set)}",
                flush=True,
            )

    if not state.get("canonical_snapshot_ready"):
        canonical = CanonicalHand().start_hand(
            hand_id=f"live-{int(state['hand_started_at'] * 1000)}",
            players=players,
            hero_cards=state.get("hero_cards", []),
            hero_position=hero_position,
            positions=positions,
            started_ts=state["hand_started_at"],
        )

        canonical.dealt_in_seats = list(dealt_in_seats)

        # Mandatory contributions are deterministic once local positions and
        # the frozen dealt-in roster are known. Seed them now; do not wait for
        # GPT name/stack enrichment.
        canonical.current_street = "PREFLOP"
        seed_forced_blinds(state, canonical)

        state["canonical_snapshot_ready"] = True
        canonical_save(canonical)

        print(
            "[CANONICAL_FAST_BOOTSTRAP] "
            f"players={len(players)} "
            f"dealer={dealer_button_seat or 'unknown'} "
            f"hero_position={hero_position}",
            flush=True,
        )

        # Events that raced ahead of the local bootstrap can now be consumed
        # chronologically. This should normally be a very small queue.
        pending_events = []

        for pending_event in list(
            state.get("pending_stack_baseline_observations") or []
        ):
            pending_events.append(
                ("stack_baseline_observation", dict(pending_event))
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

        state["pending_stack_baseline_observations"] = []
        state["pending_stack_updates"] = []
        state["pending_pot_updates"] = []
        state["pending_board_events"] = []
        state["pending_inferred_actions"] = []

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
            elif event_type == "stack_update":
                state = handle_stack_update(
                    state,
                    pending_event,
                )
            elif event_type == "pot_update":
                state = handle_pot_update(
                    state,
                    pending_event,
                )
            elif event_type == "board":
                state = handle_board(
                    state,
                    pending_event,
                )
            elif event_type == "inferred_action":
                state = handle_inferred_action(
                    state,
                    pending_event,
                )

    print(
        "[STATE] table_context "
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
    state["consumed_quantitative_commitments"] = {}
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

    if (
        event.get("purpose") == "initial"
        and event.get("forced_pot_baseline_bb") is not None
    ):
        adjustment = canonical.establish_starting_pot_adjustment(
            observed,
            float(event["forced_pot_baseline_bb"]),
        )

        print(
            "[INITIAL_POT_BASELINE] "
            f"observed={observed:.2f} "
            f"forced_baseline="
            f"{float(event['forced_pot_baseline_bb']):.2f} "
            f"adjustment={float(adjustment):.2f}",
            flush=True,
        )

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

def unresolved_board_ownership(state, street):
    """
    Return finite same-street quantitative ownership that must settle before
    canonical board promotion.

    A validated stack transition awaiting its inferred action is canonical
    action ownership.

    A provisional bet is independent quantitative commitment ownership.

    Raw stack-motion hypotheses are deliberately excluded. They are perception
    candidates, not by themselves proof that canonical action publication is
    still pending.
    """
    street = str(street or "").upper()

    awaiting_action = sorted({
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_stack_candidates")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
            and item.get("awaiting_action")
        )
    })

    provisional_bets = sorted({
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_provisional_bets")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
        )
    })

    # A raw stack-motion candidate remains only a perception hypothesis and
    # must not freeze street advancement by itself.
    #
    # Once the same candidate carries independent bet-region evidence,
    # however, a physical chip commitment is already underway. Canonical
    # board promotion must not outrun that finite quantitative lifecycle
    # merely because OCR/action classification has not completed yet.
    commitment_sources = {
        "bet_region_appeared",
        "bet_region_occupied",
    }

    commitment_candidates = sorted({
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_stack_candidates")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
            and (
                {
                    str(source)
                    for source in (
                        item.get("sources")
                        or []
                    )
                    if source
                }
                & commitment_sources
            )
        )
    })

    return {
        "awaiting_action": awaiting_action,
        "provisional_bets": provisional_bets,
        "commitment_candidates": commitment_candidates,
        "blocked": bool(
            awaiting_action
            or provisional_bets
            or commitment_candidates
        ),
    }


def release_pending_board_if_ready(state):
    """
    Promote the earliest confirmed board only after the current canonical
    betting round is semantically complete.

    Physical board visibility may race ahead of the final old-street action.
    That visual evidence is preserved, but it must never advance canonical
    street chronology while a player still owes action.
    """
    pending = list(
        state.get("pending_board_events")
        or []
    )

    if not pending:
        return state

    if not state.get("canonical_snapshot_ready"):
        return state

    canonical = canonical_load()
    tracker = tracker_for_hand(canonical)

    status = tracker.commitment_tracker.round_status(
        canonical.current_street
    )

    ownership = unresolved_board_ownership(
        state,
        canonical.current_street,
    )

    if (
        not status.get("complete")
        or ownership["blocked"]
    ):
        print(
            "[BOARD_WAIT] "
            f"street={canonical.current_street} "
            f"owing={status.get('players_owing_action')} "
            f"awaiting_action={ownership['awaiting_action']} "
            f"provisional_bets={ownership['provisional_bets']} "
            f"commitment_candidates="
            f"{ownership['commitment_candidates']} "
            f"pending={len(pending)}",
            flush=True,
        )
        return state

    pending.sort(
        key=lambda item: (
            len(item.get("board") or []),
            float(item.get("ts") or 0.0),
        )
    )

    event = pending.pop(0)
    state["pending_board_events"] = pending

    print(
        "[BOARD_RELEASE] "
        f"street={canonical.current_street} "
        f"board={event.get('board') or []} "
        f"remaining={len(pending)}",
        flush=True,
    )

    return handle_board(
        state,
        event,
    )


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
        pending = list(
            state.get("pending_board_events")
            or []
        )

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
            "waiting_for_snapshot",
            flush=True,
        )

        return state

    canonical = canonical_load()
    tracker = tracker_for_hand(canonical)

    round_status = (
        tracker.commitment_tracker.round_status(
            canonical.current_street
        )
    )

    ownership = unresolved_board_ownership(
        state,
        canonical.current_street,
    )

    if (
        not round_status.get("complete")
        or ownership["blocked"]
    ):
        pending = list(
            state.get("pending_board_events")
            or []
        )

        candidate = {
            "board": board,
            "ts": event.get("ts") or time.time(),
        }

        # Board workers may repeat the same confirmed board while an old
        # betting round is still resolving. Preserve one copy only.
        if not any(
            list(item.get("board") or []) == board
            for item in pending
        ):
            pending.append(candidate)

        pending.sort(
            key=lambda item: (
                len(item.get("board") or []),
                float(item.get("ts") or 0.0),
            )
        )

        state["pending_board_events"] = pending

        print(
            "[BOARD_WAIT] "
            f"street={canonical.current_street} "
            f"next={transition_for_board_len(n)} "
            f"owing={round_status.get('players_owing_action')} "
            f"awaiting_action={ownership['awaiting_action']} "
            f"provisional_bets={ownership['provisional_bets']} "
            f"commitment_candidates="
            f"{ownership['commitment_candidates']} "
            f"board={board}",
            flush=True,
        )

        # The asynchronous boundary worker may have completed before
        # this board became pending. Re-enter any matching preserved
        # old-street result now; otherwise both artifacts can wait on
        # each other indefinitely.
        state = (
            replay_pending_boundary_results_for_current_street(
                state
            )
        )

        return state

    next_phase = transition_for_board_len(n)

    state["phase"] = next_phase
    state["board"] = board
    state["pending_high_pot"] = None

    canonical.set_board(
        board,
        ts=event.get("ts") or time.time(),
    )
    canonical_save(canonical)

    state = record_timeline(
        state,
        f"board {next_phase} {' '.join(board)}",
    )

    print(
        f"[STATE] board -> {next_phase}",
        board,
    )

    pending_boundary = list(
        state.get("pending_boundary_results")
        or []
    )

    if pending_boundary:
        state["pending_boundary_results"] = []

        pending_boundary.sort(
            key=lambda item: float(
                item.get("ts") or 0.0
            )
        )

        still_pending = []

        for pending_result in pending_boundary:
            old = str(
                pending_result.get("street")
                or ""
            ).upper()

            expected = {
                "PREFLOP": "FLOP",
                "FLOP": "TURN",
                "TURN": "RIVER",
            }.get(old)

            if expected == next_phase:
                print(
                    "[BOUNDARY_RESULT_REPLAY] "
                    f"old={old} "
                    f"current={next_phase} "
                    f"request={str(pending_result.get('request_id') or '')[:8]}",
                    flush=True,
                )

                state = handle_boundary_stack_result(
                    state,
                    pending_result,
                )
            else:
                still_pending.append(
                    pending_result
                )

        if still_pending:
            state["pending_boundary_results"] = (
                still_pending
            )

    # The board is canonical now.
    #
    # Reconstruct physical chronology before admitting quantitative actions.
    # A later actor observed on this street may first prove passive actions by
    # earlier seats. handle_actor_observed() will itself retry quantitative
    # evidence whenever that advancement makes it admissible.
    state = replay_pending_actor_observations(
        state
    )

    # Anything not consumed by actor-observation advancement still receives
    # one ordinary retry after street promotion.
    state = replay_pending_inferred_actions(
        state
    )

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

    event_street = str(
        event.get("street") or state.get("phase") or ""
    ).upper()

    current_street = str(
        state.get("phase") or ""
    ).upper()

    canonical_street = str(
        canonical.current_street or ""
    ).upper()

    # Terminal perception may run ahead of canonical betting-round
    # reconciliation. Never reinterpret an explicitly owned future-street
    # fold as an action on whichever street canonical currently owns.
    if (
        event_street != current_street
        or event_street != canonical_street
    ):
        print(
            "[HERO_FOLD_DEFER] "
            f"event_street={event_street} "
            f"current_street={current_street} "
            f"canonical_street={canonical_street} "
            "reason=street_mismatch",
            flush=True,
        )
        return state

    already_recorded = any(
        action.seat == canonical.hero_seat
        and str(action.street or "").upper() == event_street
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

    # The fold has survived state/canonical street ownership checks above.
    # Record that causal fact so a subsequent fold-derived hand_complete
    # cannot bypass canonical action acceptance.
    state["accepted_hero_fold_street"] = event_street
    state["accepted_hero_fold_ts"] = float(
        event.get("ts") or time.time()
    )

    state["hero_to_act"] = False
    state = record_timeline(
        state,
        f"hero_fold {event.get('street') or state.get('phase')}",
    )
    return state


def unresolved_stack_candidate_seats(
    state,
    street,
):
    street = str(street or "").upper()

    return {
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_stack_candidates")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
        )
    }


def unresolved_provisional_bet_seats(
    state,
    street,
):
    """
    Return seats whose same-street provisional bet still owns unresolved
    action chronology.

    Stack-candidate ownership and provisional-bet ownership are independent
    commitment-evidence lifecycles. Either one makes passive actor skipping
    unsafe until that evidence is resolved.
    """
    street = str(street or "").upper()

    return {
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_provisional_bets")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
        )
    }


def physical_completion_stack_blocked(
    state,
    street,
    seat,
):
    """
    Return True only when an unresolved stack candidate contains
    independent commitment evidence strong enough to veto direct
    physical actor-completion evidence.

    stack_motion alone is a visual-change hypothesis. It must not
    indefinitely block calibrated opponent-card disappearance for
    the current chronological actor.

    Bet-region evidence remains a blocker because it independently
    supports chip commitment by this seat.
    """
    street = str(street or "").upper()
    seat = str(seat or "")

    candidate = (
        state.get("unresolved_stack_candidates")
        or {}
    ).get(
        f"{street}:{seat}"
    )

    if not candidate:
        return False

    sources = {
        str(source)
        for source in (
            candidate.get("sources")
            or []
        )
        if source
    }

    commitment_sources = {
        "bet_region_appeared",
        "bet_region_occupied",
    }

    blocked = bool(
        sources & commitment_sources
    )

    print(
        "[PHYSICAL_STACK_ARBITRATION] "
        f"street={street} "
        f"seat={seat} "
        f"sources={sorted(sources)} "
        f"blocked={blocked}",
        flush=True,
    )

    return blocked


def preserve_pending_actor_observation(
    state,
    event,
):
    pending = list(
        state.get("pending_actor_observations")
        or []
    )

    candidate = dict(event)

    # Same physical observation may be encountered more than once during
    # replay/reconciliation. Keep it idempotent.
    key = (
        str(candidate.get("hand_token") or ""),
        str(candidate.get("street") or "").upper(),
        str(candidate.get("seat") or ""),
        float(candidate.get("ts") or 0.0),
    )

    existing_keys = {
        (
            str(item.get("hand_token") or ""),
            str(item.get("street") or "").upper(),
            str(item.get("seat") or ""),
            float(item.get("ts") or 0.0),
        )
        for item in pending
    }

    if key not in existing_keys:
        pending.append(candidate)

    pending.sort(
        key=lambda item: float(
            item.get("ts") or 0.0
        )
    )

    state["pending_actor_observations"] = pending

    print(
        "[ACTOR_OBSERVED_DEFER] "
        f"street={candidate.get('street')} "
        f"seat={candidate.get('seat')} "
        f"pending={len(pending)}",
        flush=True,
    )

    return state


def replay_pending_actor_observations(state):
    pending = list(
        state.get("pending_actor_observations")
        or []
    )

    if not pending:
        return state

    pending.sort(
        key=lambda item: float(
            item.get("ts") or 0.0
        )
    )

    state["pending_actor_observations"] = []

    print(
        "[ACTOR_OBSERVED_REPLAY] "
        f"count={len(pending)}",
        flush=True,
    )

    for pending_event in pending:
        state = handle_actor_observed(
            state,
            pending_event,
            preserve_if_blocked=True,
        )

    return state


def player_can_acquire_commitment_ownership(
    state,
    seat,
    street,
):
    """
    Return True only when this canonical player may still acquire new
    voluntary commitment ownership.

    Perception may continue to observe visual changes at a physical seat
    after that player has folded. Those observations remain perception
    evidence only; they may never become durable poker-action ownership.
    """
    if not state.get("canonical_snapshot_ready"):
        return True

    canonical = canonical_load()
    player = canonical.players.get(seat)

    if player is None:
        return False

    if player.folded or not player.active:
        print(
            "[COMMITMENT_OWNERSHIP_REJECT] "
            f"street={street} "
            f"seat={seat} "
            f"folded={player.folded} "
            f"active={player.active}",
            flush=True,
        )
        return False

    return True


def handle_stack_candidate_opened(state, event):
    seat = str(event.get("seat") or "")
    street = str(event.get("street") or "").upper()
    event_token = str(event.get("hand_token") or "")
    current_token = str(state.get("hand_token") or "")

    if not seat or not street:
        return state

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        return state

    if not player_can_acquire_commitment_ownership(
        state,
        seat,
        street,
    ):
        return state

    candidates = dict(
        state.get("unresolved_stack_candidates")
        or {}
    )

    candidates[f"{street}:{seat}"] = {
        "seat": seat,
        "street": street,
        "sources": list(
            event.get("sources") or []
        ),
        "ts": event.get("ts"),
    }

    state["unresolved_stack_candidates"] = candidates

    print(
        "[STACK_CANDIDATE_STATE] "
        f"opened seat={seat} street={street}",
        flush=True,
    )

    return state


def handle_stack_candidate_closed(state, event):
    seat = str(event.get("seat") or "")
    street = str(event.get("street") or "").upper()
    event_token = str(event.get("hand_token") or "")
    current_token = str(state.get("hand_token") or "")

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        return state

    candidates = dict(
        state.get("unresolved_stack_candidates")
        or {}
    )

    reason = str(
        event.get("reason")
        or "candidate_removed"
    )

    candidate_key = (
        f"{street}:{seat}"
        if seat and street
        else ""
    )

    if (
        candidate_key
        and reason == "validated_stack_transition"
    ):
        # Validation proves a quantitative action exists, but the matching
        # inferred_action is produced asynchronously by ActionEpisodeManager.
        #
        # Do NOT release preserved later actors in the gap between these two
        # events. Otherwise chronology can fabricate a passive action for this
        # seat immediately before its real quantitative action arrives.
        candidate = dict(
            candidates.get(candidate_key)
            or {}
        )

        candidate.update({
            "seat": seat,
            "street": street,
            "awaiting_action": True,
            "resolved_reason": reason,
            "resolved_ts": event.get("ts"),
        })

        candidates[candidate_key] = candidate
        state["unresolved_stack_candidates"] = candidates

        print(
            "[STACK_CANDIDATE_STATE] "
            f"resolved_waiting_action seat={seat} "
            f"street={street} "
            f"reason={reason}",
            flush=True,
        )

        return state

    if candidate_key:
        candidates.pop(
            candidate_key,
            None,
        )

    state["unresolved_stack_candidates"] = candidates

    print(
        "[STACK_CANDIDATE_STATE] "
        f"closed seat={seat} street={street} "
        f"reason={reason}",
        flush=True,
    )

    # Stack ownership is only one commitment-evidence lifecycle.
    # A separate provisional absolute-bet observation may still make
    # passive chronology unsafe for this same seat/street.
    provisional = (
        state.get("unresolved_provisional_bets")
        or {}
    )

    provisional_key = (
        f"{street}:{seat}"
        if seat and street
        else ""
    )

    if (
        provisional_key
        and provisional_key in provisional
    ):
        print(
            "[STACK_CANDIDATE_STATE] "
            f"closed seat={seat} street={street} "
            "chronology_release=deferred "
            "reason=provisional_bet_unresolved",
            flush=True,
        )

        return state

    # No commitment-evidence owner remains for this candidate.
    # Preserved later actors may now be reconsidered.
    state = replay_pending_actor_observations(
        state
    )

    # Retrospective boundary evidence may also have been preserved while this
    # same stack candidate made semantic promotion unsafe. Candidate removal
    # is the causal point at which that evidence becomes eligible for the
    # existing boundary resolver again.
    state = replay_preserved_boundary_evidence(
        state,
        street=street,
    )

    return state


def handle_provisional_bet_opened(state, event):
    seat = str(event.get("seat") or "")
    street = str(event.get("street") or "").upper()
    event_token = str(event.get("hand_token") or "")
    current_token = str(state.get("hand_token") or "")

    if not seat or not street:
        return state

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        return state

    if not player_can_acquire_commitment_ownership(
        state,
        seat,
        street,
    ):
        return state

    key = f"{street}:{seat}"

    consumed = (
        state.get("consumed_quantitative_commitments")
        or {}
    )

    if key in consumed:
        print(
            "[PROVISIONAL_BET_STATE] "
            f"ignored_late_open seat={seat} "
            f"street={street} "
            "reason=quantitative_commitment_already_consumed",
            flush=True,
        )
        return state

    blockers = dict(
        state.get("unresolved_provisional_bets")
        or {}
    )

    blockers[f"{street}:{seat}"] = {
        "seat": seat,
        "street": street,
        "source": event.get(
            "source",
            "transition",
        ),
        "source_request_id": event.get(
            "source_request_id"
        ),
        "bet_bb": event.get("bet_bb"),
        "ts": event.get("ts"),
    }

    state[
        "unresolved_provisional_bets"
    ] = blockers

    print(
        "[PROVISIONAL_BET_STATE] "
        f"opened seat={seat} "
        f"street={street}",
        flush=True,
    )

    state = refresh_live_presentation(
        state
    )

    return state


def handle_provisional_bet_closed(state, event):
    seat = str(event.get("seat") or "")
    street = str(event.get("street") or "").upper()
    event_token = str(event.get("hand_token") or "")
    current_token = str(state.get("hand_token") or "")

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        return state

    key = (
        f"{street}:{seat}"
        if seat and street
        else ""
    )

    blockers = dict(
        state.get("unresolved_provisional_bets")
        or {}
    )

    if key:
        blockers.pop(
            key,
            None,
        )

    state[
        "unresolved_provisional_bets"
    ] = blockers

    print(
        "[PROVISIONAL_BET_STATE] "
        f"closed seat={seat} "
        f"street={street} "
        f"reason={event.get('reason') or 'resolved'}",
        flush=True,
    )

    state = replay_pending_actor_observations(
        state
    )

    state = replay_pending_inferred_actions(
        state
    )

    state = refresh_live_presentation(
        state
    )

    return state


def handle_actor_observed(
    state,
    event,
    *,
    preserve_if_blocked=True,
):
    """
    Advance canonical action chronology to a physically observed actor.

    This event carries chronology evidence only. It does NOT classify the
    observed actor's action or assign sizing. Earlier seats may be resolved
    passively only when no unresolved same-street commitment evidence blocks
    the gap.
    """
    if state.get("phase") == "WAITING":
        print("[SKIP] actor_observed while waiting", event)
        return state

    if not state.get("canonical_snapshot_ready"):
        print(
            "[SKIP] actor_observed before canonical bootstrap "
            f"seat={event.get('seat')}",
            flush=True,
        )
        return state

    seat = str(event.get("seat") or "")
    event_street = str(
        event.get("street") or state.get("phase") or ""
    ).upper()
    current_street = str(state.get("phase") or "").upper()

    if not seat:
        return state

    if event_street != current_street:
        # Physical chronology may already have entered the immediately next
        # street while canonical chronology is still completing the prior
        # street behind a confirmed pending board.
        #
        # Observing a later actor on that next street is durable chronology
        # evidence: once the board is promoted it may safely resolve passive
        # predecessors through the ordinary actor_observed path.
        next_street = {
            "PREFLOP": "FLOP",
            "FLOP": "TURN",
            "TURN": "RIVER",
        }.get(current_street)

        matching_pending_board = any(
            transition_for_board_len(
                len(item.get("board") or [])
            )
            == event_street
            for item in (
                state.get("pending_board_events")
                or []
            )
            if isinstance(item, dict)
        )

        if (
            preserve_if_blocked
            and event_street == next_street
            and matching_pending_board
        ):
            state = preserve_pending_actor_observation(
                state,
                event,
            )

            print(
                "[ACTOR_OBSERVED_FUTURE_PRESERVED] "
                f"street={event_street} "
                f"current={current_street} "
                f"actor={seat} "
                "reason=confirmed_pending_board",
                flush=True,
            )

            return state

        print(
            "[ACTOR_OBSERVED_SKIP] "
            f"seat={seat} "
            f"event_street={event_street} "
            f"current_street={current_street} "
            "reason=street_mismatch",
            flush=True,
        )
        return state

    event_token = str(event.get("hand_token") or "")
    current_token = str(state.get("hand_token") or "")

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        print(
            "[ACTOR_OBSERVED_SKIP] "
            f"seat={seat} reason=hand_token_mismatch",
            flush=True,
        )
        return state

    canonical = canonical_load()

    if str(canonical.current_street or "").upper() != event_street:
        print(
            "[ACTOR_OBSERVED_SKIP] "
            f"seat={seat} "
            f"canonical_street={canonical.current_street} "
            f"event_street={event_street} "
            "reason=canonical_street_mismatch",
            flush=True,
        )
        return state

    if seat not in canonical.players:
        print(
            "[ACTOR_OBSERVED_SKIP] "
            f"seat={seat} reason=unknown_seat",
            flush=True,
        )
        return state

    blocked_seats = unresolved_stack_candidate_seats(
        state,
        event_street,
    )

    blocked_seats.update(
        unresolved_provisional_bet_seats(
            state,
            event_street,
        )
    )

    # Stack candidates and provisional bets are independent commitment
    # evidence lifecycles. Either one prevents a later observed actor from
    # fabricating a passive action through the unresolved seat.
    #
    # The coordinator may observe stack motion and a later actor in the same
    # local frame. api_events.jsonl has not necessarily delivered the
    # stack_candidate_opened event yet, so preserve those same-frame seats as
    # conservative chronology blockers directly on actor_observed.
    blocked_seats.update(
        str(seat)
        for seat in (event.get("blocked_seats") or [])
        if seat
    )

    tracker = tracker_for_hand(canonical)

    queue_before = list(
        canonical.players_to_act or []
    )

    actor_index = (
        queue_before.index(seat)
        if seat in queue_before
        else -1
    )

    skipped_before = (
        queue_before[:actor_index]
        if actor_index > 0
        else []
    )

    blocking_gap = [
        skipped_seat
        for skipped_seat in skipped_before
        if skipped_seat in blocked_seats
    ]

    added = tracker.advance_to_observed_actor(
        seat,
        ts=event.get("ts") or time.time(),
        blocked_seats=blocked_seats,
    )

    if (
        not added
        and blocking_gap
        and preserve_if_blocked
    ):
        state = preserve_pending_actor_observation(
            state,
            event,
        )

        print(
            "[ACTOR_OBSERVED_BLOCKED_PRESERVED] "
            f"street={event_street} "
            f"actor={seat} "
            f"blocked={blocking_gap}",
            flush=True,
        )

        return state

    if added:
        canonical_save(canonical)

        for action in added:
            print(
                "[CANONICAL_ACTION_ORDER] "
                f"{action.street} "
                f"{action.seat} "
                f"{action.action} "
                f"trigger_actor={seat}",
                flush=True,
            )

            state = record_timeline(
                state,
                "action_order "
                f"{action.street} "
                f"{action.seat} "
                f"{action.action}",
            )

        write_betting_round_status(
            tracker,
            canonical,
            state,
        )

        state = replay_pending_physical_actor_completions(
            state
        )

        # Chronology is authoritative now. Give the fastest trustworthy
        # physical presentation one TXT write before quantitative settlement
        # can overtake it.
        state = record_physical_live_commitment(
            state,
            event,
        )

        # Chronology advancement may make an already-qualified quantitative
        # action admissible. Retry it only after the physical presentation
        # has had a chance to reach current_hand.txt.
        pending = list(
            state.get("pending_inferred_actions")
            or []
        )

        if pending:
            state["pending_inferred_actions"] = []

            pending.sort(
                key=lambda item: float(
                    item.get("ts") or 0.0
                )
            )

            print(
                "[REPLAY] actor_observed retrying "
                f"{len(pending)} deferred inferred actions",
                flush=True,
            )

            for pending_event in pending:
                state = handle_inferred_action(
                    state,
                    pending_event,
                )

        return state

    state = record_physical_live_commitment(
        state,
        event,
    )

    return state


def preserve_physical_actor_completion(
    state,
    event,
):
    pending = list(
        state.get(
            "pending_physical_actor_completions"
        )
        or []
    )

    key = (
        str(event.get("hand_token") or ""),
        str(event.get("street") or "").upper(),
        str(event.get("seat") or ""),
    )

    existing = {
        (
            str(item.get("hand_token") or ""),
            str(item.get("street") or "").upper(),
            str(item.get("seat") or ""),
        )
        for item in pending
    }

    if key not in existing:
        pending.append(dict(event))

    pending.sort(
        key=lambda item: float(
            item.get("ts") or 0.0
        )
    )

    state[
        "pending_physical_actor_completions"
    ] = pending

    return state


def replay_pending_physical_actor_completions(
    state,
):
    pending = list(
        state.get(
            "pending_physical_actor_completions"
        )
        or []
    )

    if not pending:
        return state

    state[
        "pending_physical_actor_completions"
    ] = []

    pending.sort(
        key=lambda item: float(
            item.get("ts") or 0.0
        )
    )

    for pending_event in pending:
        state = handle_physical_actor_completed(
            state,
            pending_event,
            preserve_if_blocked=True,
        )

    return state


def handle_physical_actor_completed(
    state,
    event,
    *,
    preserve_if_blocked=True,
):
    """
    Consume neutral physical completion evidence only when that seat
    is the current head of canonical players_to_act.

    Evidence for a later seat is preserved. It can never jump an
    unresolved earlier actor.
    """
    if state.get("phase") == "WAITING":
        return state

    if not state.get("canonical_snapshot_ready"):
        if preserve_if_blocked:
            return preserve_physical_actor_completion(
                state,
                event,
            )
        return state

    seat = str(
        event.get("seat")
        or ""
    )

    event_street = str(
        event.get("street")
        or state.get("phase")
        or ""
    ).upper()

    current_street = str(
        state.get("phase")
        or ""
    ).upper()

    if not seat:
        return state

    if event_street != current_street:
        print(
            "[PHYSICAL_ACTOR_SKIP] "
            f"seat={seat} "
            f"event_street={event_street} "
            f"current_street={current_street} "
            "reason=street_mismatch",
            flush=True,
        )
        return state

    event_token = str(
        event.get("hand_token")
        or ""
    )

    current_token = str(
        state.get("hand_token")
        or ""
    )

    if (
        event_token
        and current_token
        and event_token != current_token
    ):
        return state

    canonical = canonical_load()

    if (
        str(
            canonical.current_street
            or ""
        ).upper()
        != event_street
    ):
        return state

    if seat not in canonical.players:
        return state

    queue = list(
        canonical.players_to_act
        or []
    )

    if not queue:
        return state

    if queue[0] != seat:
        # A later physical completion is also chronology evidence that all
        # earlier seats have already completed their actions. Reuse the
        # existing actor_observed path, which may resolve only safe passive
        # predecessors and is blocked by unresolved commitment evidence.
        state = handle_actor_observed(
            state,
            {
                "type": "actor_observed",
                "hand_token": event_token,
                "seat": seat,
                "street": event_street,
                "source": (
                    event.get("source")
                    or "physical_actor_completed"
                ),
                "blocked_seats": list(
                    event.get("blocked_seats")
                    or []
                ),
                "ts": event.get("ts") or time.time(),
            },
            preserve_if_blocked=preserve_if_blocked,
        )

        # actor_observed may have advanced the queue through missed passive
        # predecessors. Reload the canonical hand before applying the direct
        # head-only physical completion.
        canonical = canonical_load()
        queue = list(
            canonical.players_to_act
            or []
        )

        if not queue or queue[0] != seat:
            if preserve_if_blocked:
                state = preserve_physical_actor_completion(
                    state,
                    event,
                )

            print(
                "[PHYSICAL_ACTOR_PENDING] "
                f"street={event_street} "
                f"seat={seat} "
                f"head={queue[0] if queue else None}",
                flush=True,
            )

            return state

    # Do not resolve through unresolved quantitative commitment evidence.
    if physical_completion_stack_blocked(
        state,
        event_street,
        seat,
    ):
        if preserve_if_blocked:
            state = preserve_physical_actor_completion(
                state,
                event,
            )

        print(
            "[PHYSICAL_ACTOR_PENDING] "
            f"street={event_street} "
            f"seat={seat} "
            "reason=unresolved_stack_candidate",
            flush=True,
        )

        return state

    tracker = tracker_for_hand(
        canonical
    )

    added = (
        tracker.resolve_physically_completed_actor(
            seat,
            ts=event.get("ts") or time.time(),
        )
    )

    if not added:
        if preserve_if_blocked:
            state = preserve_physical_actor_completion(
                state,
                event,
            )
        return state

    canonical_save(
        canonical
    )

    for action in added:
        print(
            "[CANONICAL_PHYSICAL_ACTION] "
            f"{action.street} "
            f"{action.seat} "
            f"{action.action}",
            flush=True,
        )

        state = record_timeline(
            state,
            "physical_action "
            f"{action.street} "
            f"{action.seat} "
            f"{action.action}",
        )

    write_betting_round_status(
        tracker,
        canonical,
        state,
    )

    # Head advancement may make another preserved physical
    # completion immediately admissible.
    state = (
        replay_pending_physical_actor_completions(
            state
        )
    )

    # It may also unblock normal deferred quantitative actions.
    pending = list(
        state.get("pending_inferred_actions")
        or []
    )

    if pending:
        state[
            "pending_inferred_actions"
        ] = []

        pending.sort(
            key=lambda item: float(
                item.get("ts") or 0.0
            )
        )

        for pending_event in pending:
            state = handle_inferred_action(
                state,
                pending_event,
            )

    return state


def preserve_pending_inferred_action(
    state,
    event,
):
    pending = list(
        state.get("pending_inferred_actions")
        or []
    )

    key = (
        str(event.get("hand_token") or ""),
        str(event.get("street") or "").upper(),
        str(event.get("seat") or ""),
        str(event.get("action") or ""),
        float(event.get("ts") or 0.0),
    )

    existing = {
        (
            str(item.get("hand_token") or ""),
            str(item.get("street") or "").upper(),
            str(item.get("seat") or ""),
            str(item.get("action") or ""),
            float(item.get("ts") or 0.0),
        )
        for item in pending
    }

    if key not in existing:
        pending.append(
            dict(event)
        )

    pending.sort(
        key=lambda item: float(
            item.get("ts")
            or 0.0
        )
    )

    state[
        "pending_inferred_actions"
    ] = pending

    return state


def replay_pending_inferred_actions(
    state,
):
    pending = list(
        state.get("pending_inferred_actions")
        or []
    )

    if not pending:
        return state

    state[
        "pending_inferred_actions"
    ] = []

    pending.sort(
        key=lambda item: float(
            item.get("ts")
            or 0.0
        )
    )

    print(
        "[REPLAY] retrying "
        f"{len(pending)} "
        "deferred inferred actions",
        flush=True,
    )

    for pending_event in pending:
        state = handle_inferred_action(
            state,
            pending_event,
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

    action_street = str(
        event.get("street") or ""
    ).upper()

    unsettled_stack_evidence_seats = sorted({
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_stack_candidates")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == action_street
            and item.get("seat")
        )
    })

    tracker_event = dict(event)
    tracker_event[
        "unsettled_stack_evidence_seats"
    ] = unsettled_stack_evidence_seats

    canonical_street = str(
        canonical.current_street or ""
    ).upper()

    if (
        action_street
        and action_street != canonical_street
    ):
        # A confirmed next-street board may be physically visible while
        # canonical chronology is still resolving the previous street.
        #
        # Quantitative evidence explicitly owned by that immediately-next
        # street is future evidence, not stale evidence. Preserve it until
        # the pending board becomes canonical rather than submitting it to
        # the current-street tracker, where it would be rejected.
        next_street = {
            "PREFLOP": "FLOP",
            "FLOP": "TURN",
            "TURN": "RIVER",
        }.get(canonical_street)

        matching_pending_board = any(
            transition_for_board_len(
                len(item.get("board") or [])
            )
            == action_street
            for item in (
                state.get("pending_board_events")
                or []
            )
            if isinstance(item, dict)
        )

        if (
            action_street == next_street
            and matching_pending_board
        ):
            state = preserve_pending_inferred_action(
                state,
                event,
            )

            print(
                "[CANONICAL_DEFER_FUTURE_STREET] "
                f"street={action_street} "
                f"current={canonical_street} "
                f"seat={seat} "
                f"action={event.get('action')} "
                "reason=confirmed_pending_board",
                flush=True,
            )

            return state

        evidence_key = (
            f"{str(state.get('hand_token') or '')}:"
            f"{action_street}"
        )

        preserved_boundary = (
            state.get("preserved_boundary_evidence")
            or {}
        )

        if evidence_key in preserved_boundary:
            state = preserve_old_street_inferred_action(
                state,
                tracker_event,
            )

            state, reconciled = (
                reconcile_preserved_inferred_actions(
                    state,
                    hand_token=state.get("hand_token"),
                    street=action_street,
                )
            )

            if reconciled:
                state = record_timeline(
                    state,
                    "preserved_action_reconciled "
                    f"{action_street}",
                )

                return state

            print(
                "[CANONICAL_DEFER_OLD_STREET] "
                f"street={action_street} "
                f"current={canonical_street} "
                f"seat={seat} "
                f"action={event.get('action')} "
                "reason=preserved_boundary_context",
                flush=True,
            )

            return state

    provisional_blockers = {
        str(item.get("seat") or "")
        for item in (
            state.get(
                "unresolved_provisional_bets"
            )
            or {}
        ).values()
        if (
            str(
                item.get("street")
                or ""
            ).upper()
            == action_street
            and item.get("seat")
        )
    }

    # StreetCommitmentTracker owns authoritative outstanding poker
    # chronology. canonical.players_to_act is a materialized hand field and
    # may temporarily lag after boundary/historical reconciliation.
    #
    # Quantitative admission must therefore derive predecessor ownership from
    # the tracker rather than from the potentially stale materialized queue.
    queue = list(
        tracker.commitment_tracker.players_owing_action(
            action_street
        )
        or []
    )

    actor_index = (
        queue.index(seat)
        if seat in queue
        else -1
    )

    earlier_seats = (
        queue[:actor_index]
        if actor_index > 0
        else []
    )

    provisional_gap = [
        earlier_seat
        for earlier_seat in earlier_seats
        if earlier_seat
        in provisional_blockers
    ]

    # A player may already have acted earlier on this street and therefore
    # no longer appear in players_to_act. Unresolved aggression by another
    # seat can legitimately reopen action for that player.
    #
    # Until that provisional aggression resolves, a later quantitative
    # stack decrease from the previously acted player cannot be classified
    # as fresh aggression merely because the player is absent from the
    # current action queue.
    #
    # Exclude the incoming seat itself: its quantitative action must remain
    # eligible to resolve its own provisional commitment.
    provisional_reentry_gap = (
        sorted(
            provisional_blockers
            - {str(seat or "")}
        )
        if actor_index < 0
        else []
    )

    provisional_blocking_seats = (
        provisional_gap
        if provisional_gap
        else provisional_reentry_gap
    )

    if provisional_blocking_seats:
        state = (
            preserve_pending_inferred_action(
                state,
                event,
            )
        )

        mode = (
            "queue_gap"
            if provisional_gap
            else "reentry"
        )

        print(
            "[QUANTITATIVE_PROVISIONAL_DEFER] "
            f"street={action_street} "
            f"seat={seat} "
            f"blocked={provisional_blocking_seats} "
            f"mode={mode}",
            flush=True,
        )

        return state

    added = tracker.ingest(tracker_event)

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
                state = preserve_pending_inferred_action(
                    state,
                    event,
                )

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

    # Canonical quantitative ingestion is the irreversible semantic boundary
    # for this physical commitment. Preserve that ownership fact so a slower
    # asynchronous bet-sizing result cannot later recreate a provisional
    # blocker for the same hand/street/seat.
    consumed_key = (
        f"{str(added.street or '').upper()}:"
        f"{str(added.seat or '')}"
    )

    consumed = dict(
        state.get("consumed_quantitative_commitments")
        or {}
    )

    consumed[consumed_key] = {
        "seat": str(added.seat or ""),
        "street": str(added.street or "").upper(),
        "action": str(added.action or ""),
        "ts": event.get("ts"),
    }

    state["consumed_quantitative_commitments"] = consumed

    # A validated stack candidate remains a chronology blocker until the
    # corresponding quantitative inferred_action is actually canonical.
    #
    # Release it only after tracker.ingest() succeeds. Deferred/rejected
    # actions return above and therefore keep their blocker intact.
    candidates = dict(
        state.get("unresolved_stack_candidates")
        or {}
    )

    candidate_key = (
        f"{str(added.street or '').upper()}:"
        f"{str(added.seat or '')}"
    )

    candidate = candidates.get(
        candidate_key
    )

    if (
        isinstance(candidate, dict)
        and candidate.get("awaiting_action")
    ):
        candidates.pop(
            candidate_key,
            None,
        )

        state["unresolved_stack_candidates"] = (
            candidates
        )

        print(
            "[STACK_CANDIDATE_STATE] "
            f"action_consumed seat={added.seat} "
            f"street={added.street}",
            flush=True,
        )

        # The real quantitative action is canonical now. Only now is it safe
        # to reconsider physical observations of later actors that were
        # preserved behind this commitment.
        state = replay_pending_actor_observations(
            state
        )

    state = replay_pending_physical_actor_completions(
        state
    )

    state = replay_pending_inferred_actions(
        state
    )

    # A physical next-street board may already be waiting. The action just
    # accepted above can be the final obligation on the old street, so promote
    # that board immediately rather than waiting for another unrelated event.
    state = release_pending_board_if_ready(
        state
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

    normalized_result = str(result).strip().lower()
    fold_prefix = "hero folded on "

    if normalized_result.startswith(fold_prefix):
        claimed_street = (
            normalized_result[len(fold_prefix):]
            .strip()
            .upper()
        )

        accepted_street = str(
            state.get("accepted_hero_fold_street")
            or ""
        ).upper()

        if (
            not accepted_street
            or accepted_street != claimed_street
        ):
            print(
                "[HAND_COMPLETE_REJECT] "
                f"result={result!r} "
                f"claimed_street={claimed_street or 'unknown'} "
                f"accepted_hero_fold_street="
                f"{accepted_street or 'none'} "
                "reason=missing_accepted_fold_cause",
                flush=True,
            )

            state = record_timeline(
                state,
                "hand_complete_rejected "
                "missing_accepted_fold_cause",
            )

            return state

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


def preserve_boundary_evidence(state, result):
    """
    Retain objective old-street boundary evidence until that preserved
    betting round is semantically complete.

    This is evidence storage only. It assigns no poker action.
    """
    hand_token = str(
        result.get("hand_token") or ""
    )

    street = str(
        result.get("street") or ""
    ).upper()

    if (
        not hand_token
        or street not in (
            "PREFLOP",
            "FLOP",
            "TURN",
        )
    ):
        return state

    store = dict(
        state.get("preserved_boundary_evidence")
        or {}
    )

    key = f"{hand_token}:{street}"

    existing = dict(
        store.get(key) or {}
    )

    observations_by_seat = dict(
        existing.get("observations_by_seat")
        or {}
    )

    for item in list(
        result.get("observations") or []
    ):
        if not isinstance(item, dict):
            continue

        seat = str(
            item.get("seat") or ""
        )

        observation = item.get("observation")

        if (
            not seat
            or not isinstance(observation, dict)
        ):
            continue

        observations_by_seat[seat] = {
            "seat": seat,
            "observation": dict(observation),
        }

    existing.update({
        "hand_token": hand_token,
        "street": street,
        "request_id": str(
            result.get("request_id") or ""
        ),
        "observations_by_seat": (
            observations_by_seat
        ),
        "last_result_ts": (
            result.get("ts")
            or time.time()
        ),
    })

    store[key] = existing
    state["preserved_boundary_evidence"] = store

    print(
        "[BOUNDARY_EVIDENCE_PRESERVED] "
        f"street={street} "
        f"seats={list(observations_by_seat)} "
        f"request={existing['request_id'][:8]}",
        flush=True,
    )

    return state


def replay_preserved_boundary_evidence(
    state,
    *,
    street,
):
    """
    Reconsider durable old-street boundary evidence after a commitment
    blocker disappears.

    The original boundary handler intentionally preserves objective evidence
    when unresolved quantitative ownership prevents semantic promotion.
    Once that blocker is gone, this helper re-enters the same existing
    boundary semantic path rather than inventing a parallel action rule.
    """
    hand_token = str(
        state.get("hand_token")
        or ""
    )

    street = str(
        street
        or ""
    ).upper()

    if (
        not hand_token
        or street not in (
            "PREFLOP",
            "FLOP",
            "TURN",
        )
    ):
        return state

    store = (
        state.get("preserved_boundary_evidence")
        or {}
    )

    key = f"{hand_token}:{street}"

    bucket = store.get(key)

    if not isinstance(bucket, dict):
        return state

    observations_by_seat = dict(
        bucket.get("observations_by_seat")
        or {}
    )

    if not observations_by_seat:
        return state

    result = {
        "type": "boundary_stack_result",
        "request_id": (
            bucket.get("request_id")
            or f"preserved-{street.lower()}"
        ),
        "hand_token": hand_token,
        "street": street,
        "ts": (
            bucket.get("last_result_ts")
            or time.time()
        ),
        "observations": [
            dict(item)
            for item in observations_by_seat.values()
            if isinstance(item, dict)
        ],
    }

    print(
        "[BOUNDARY_EVIDENCE_REPLAY] "
        f"street={street} "
        f"seats={list(observations_by_seat)}",
        flush=True,
    )

    return handle_boundary_stack_result(
        state,
        result,
        reconsider_observed_after_candidate_release=True,
    )


def preserve_old_street_inferred_action(
    state,
    event,
):
    """
    Retain one already-qualified inferred action for historical reconciliation.

    This does not assign canonical semantics and is not a stale-action bypass.
    """
    hand_token = str(
        state.get("hand_token") or ""
    )

    street = str(
        event.get("street") or ""
    ).upper()

    seat = str(
        event.get("seat") or ""
    )

    if (
        not hand_token
        or street not in (
            "PREFLOP",
            "FLOP",
            "TURN",
        )
        or not seat
    ):
        return state

    store = dict(
        state.get("preserved_inferred_actions")
        or {}
    )

    key = f"{hand_token}:{street}"

    bucket = dict(
        store.get(key) or {}
    )

    by_seat = dict(
        bucket.get("actions_by_seat")
        or {}
    )

    existing = by_seat.get(seat)

    # Keep the strongest/latest qualified evidence for one seat while
    # remaining deterministic under duplicate event delivery.
    if existing is None:
        by_seat[seat] = dict(event)
    else:
        existing_confidence = float(
            existing.get("confidence") or 0.0
        )
        new_confidence = float(
            event.get("confidence") or 0.0
        )

        existing_ts = float(
            existing.get("ts") or 0.0
        )
        new_ts = float(
            event.get("ts") or 0.0
        )

        if (
            new_confidence > existing_confidence
            or (
                new_confidence == existing_confidence
                and new_ts >= existing_ts
            )
        ):
            by_seat[seat] = dict(event)

    bucket.update({
        "hand_token": hand_token,
        "street": street,
        "actions_by_seat": by_seat,
    })

    store[key] = bucket
    state["preserved_inferred_actions"] = store

    print(
        "[OLD_STREET_ACTION_PRESERVED] "
        f"street={street} "
        f"seat={seat} "
        f"action={event.get('action')} "
        f"delta={event.get('delta_bb')}",
        flush=True,
    )

    return state


def reconcile_preserved_inferred_actions(
    state,
    *,
    hand_token,
    street,
):
    """
    Promote a complete qualified historical PREFLOP sequence immediately.

    This repairs event arrival order only. It does not weaken the normal
    BettingRoundTracker stale-street contract and it does not manufacture
    semantics for a committed player whose own qualified event is absent.
    """
    hand_token = str(hand_token or "")
    street = str(street or "").upper()

    if not hand_token or not street:
        return state, False

    key = f"{hand_token}:{street}"

    store = (
        state.get("preserved_inferred_actions")
        or {}
    )

    bucket = store.get(key)

    if not isinstance(bucket, dict):
        return state, False

    qualified = dict(
        bucket.get("actions_by_seat")
        or {}
    )

    if not qualified:
        return state, False

    canonical = canonical_load()
    tracker = tracker_for_hand(canonical)

    reconciliation = reconcile_preserved_actions(
        hand=canonical,
        commitment_tracker=tracker.commitment_tracker,
        street=street,
        qualified_actions=qualified,
    )

    if not reconciliation.resolved:
        print(
            "[PRESERVED_ACTION_RECONCILE_WAIT] "
            f"street={street} "
            f"reason={reconciliation.reason}",
            flush=True,
        )
        return state, False

    # Historical actions already present are never duplicated.
    existing = {
        (
            str(action.street or "").upper(),
            action.seat,
            action.action,
        )
        for action in canonical.actions
    }

    added = []

    for item in reconciliation.actions:
        identity = (
            street,
            item["seat"],
            item["action"],
        )

        if identity in existing:
            continue

        action = canonical.add_boundary_action(
            street=street,
            seat=item["seat"],
            action=item["action"],
            amount_bb=item.get("amount_bb"),
            raise_to_bb=item.get("raise_to_bb"),
            confidence=item.get("confidence"),
            source=item.get("source"),
            evidence=item.get("evidence"),
            ts=item.get("ts"),
        )

        existing.add(identity)

        added.append(
            (
                action.seat,
                action.action,
            )
        )

    if not added:
        return state, False

    # The reconstructed sequence is complete through its latest qualified
    # actor. Rebuild only the preserved OLD-STREET obligation state.
    #
    # This does not touch CanonicalHand.current_street, players_to_act,
    # current_bet_bb, or last_aggressor_seat for the live street.
    old_state = tracker.commitment_tracker._state(
        street
    )

    old_order = list(
        old_state.street_order
        or []
    )

    tracker.commitment_tracker.reset_street(
        street
    )

    tracker.commitment_tracker.initialize_street_order(
        street,
        old_order,
    )

    tracker.commitment_tracker.sync_queue(
        street,
        old_order,
    )

    for item in reconciliation.actions:
        seat = item["seat"]
        action = item["action"]

        if action == "FOLD":
            tracker.commitment_tracker.consume_pending_action(
                street,
                seat,
            )

            tracker.commitment_tracker.record_action(
                street,
                seat,
            )

            continue

        tracker.commitment_tracker.record_commitment(
            street,
            seat,
        )

        if action == "RAISE":
            tracker.commitment_tracker.consume_pending_action(
                street,
                seat,
            )

            eligible = [
                candidate
                for candidate in old_order
                if candidate != seat
                and canonical.players.get(candidate)
                and canonical.players[candidate].active
                and not canonical.players[candidate].folded
                and not canonical.players[candidate].all_in
            ]

            tracker.commitment_tracker.open_response_queue(
                street,
                seat,
                eligible,
            )

            tracker.commitment_tracker.record_action(
                street,
                seat,
                current_price=float(
                    item.get("raise_to_bb")
                    or 0.0
                ),
                last_aggressor=seat,
                betting_open=True,
            )

            continue

        # CALL
        status = (
            tracker.commitment_tracker
            .round_status(street)
        )

        if status.get("betting_open"):
            tracker.commitment_tracker.record_response(
                street,
                seat,
            )
        else:
            tracker.commitment_tracker.consume_pending_action(
                street,
                seat,
            )

        tracker.commitment_tracker.record_action(
            street,
            seat,
        )

    canonical_save(canonical)

    print(
        "[PRESERVED_ACTION_RECONCILED] "
        f"street={street} "
        f"actions={added}",
        flush=True,
    )

    # A validated quantitative stack candidate remains a chronology blocker
    # until its corresponding inferred_action is actually canonical.
    #
    # Historical reconciliation is another canonicalization path, so it must
    # complete the same transaction as the ordinary tracker.ingest() path.
    # Only consume candidates for seats that supplied qualified quantitative
    # evidence to this successful reconciliation. Passive reconstructed seats
    # must never consume unrelated stack candidates.
    candidates = dict(
        state.get("unresolved_stack_candidates")
        or {}
    )

    consumed_candidate = False

    for qualified_seat in qualified:
        candidate_key = (
            f"{street}:{qualified_seat}"
        )

        candidate = candidates.get(
            candidate_key
        )

        if (
            isinstance(candidate, dict)
            and candidate.get("awaiting_action")
        ):
            candidates.pop(
                candidate_key,
                None,
            )

            consumed_candidate = True

            print(
                "[STACK_CANDIDATE_STATE] "
                f"action_consumed seat={qualified_seat} "
                f"street={street} "
                "path=preserved_reconciliation",
                flush=True,
            )

    if consumed_candidate:
        state["unresolved_stack_candidates"] = (
            candidates
        )

        # Match the ordinary canonical-action transaction: once the real
        # quantitative action owns this commitment, chronology that was held
        # behind its blocker may safely be reconsidered.
        state = replay_pending_actor_observations(
            state
        )

    state = clear_preserved_inferred_actions(
        state,
        hand_token=hand_token,
        street=street,
    )

    state = clear_preserved_boundary_evidence(
        state,
        hand_token=hand_token,
        street=street,
    )

    write_betting_round_status(
        tracker,
        canonical,
        state,
    )

    return state, True


def clear_preserved_inferred_actions(
    state,
    *,
    hand_token,
    street,
):
    store = dict(
        state.get("preserved_inferred_actions")
        or {}
    )

    key = (
        f"{str(hand_token or '')}:"
        f"{str(street or '').upper()}"
    )

    if key in store:
        store.pop(key, None)
        state["preserved_inferred_actions"] = store

        print(
            "[OLD_STREET_ACTIONS_CLEARED] "
            f"street={str(street or '').upper()}",
            flush=True,
        )

    return state


def clear_preserved_boundary_evidence(
    state,
    *,
    hand_token,
    street,
):
    store = dict(
        state.get("preserved_boundary_evidence")
        or {}
    )

    key = (
        f"{str(hand_token or '')}:"
        f"{str(street or '').upper()}"
    )

    if key in store:
        store.pop(key, None)
        state["preserved_boundary_evidence"] = store

        print(
            "[BOUNDARY_EVIDENCE_CLEARED] "
            f"street={str(street or '').upper()}",
            flush=True,
        )

    return state


def boundary_can_resolve_passively_without_stack_ocr(
    *,
    street,
    betting_open,
    current_price,
    last_aggressor,
    unresolved_candidates,
    provisional_bets,
    commitment_candidates,
):
    """
    True only when a confirmed next-street boundary closes an
    genuinely unopened postflop street with no surviving quantitative
    or physical commitment ownership.

    This predicate does not itself resolve actions or advance streets.
    """
    street = str(
        street
        or ""
    ).upper()

    if street not in {
        "FLOP",
        "TURN",
    }:
        return False

    if betting_open:
        return False

    try:
        price = float(
            current_price
            or 0.0
        )
    except (TypeError, ValueError):
        return False

    if abs(price) > 1e-9:
        return False

    if last_aggressor:
        return False

    if set(
        unresolved_candidates
        or []
    ):
        return False

    if set(
        provisional_bets
        or []
    ):
        return False

    if set(
        commitment_candidates
        or []
    ):
        return False

    return True


def boundary_observation_must_block_passive_resolution(
    *,
    seat,
    observed_seats,
    unresolved_candidates,
    preserved_actions,
    reconsider_observed_after_candidate_release=False,
):
    """
    Decide whether an explicit boundary observation still owns enough
    semantic authority to veto passive old-street resolution.

    An observation by itself is not commitment ownership. It remains a
    blocker only while surviving quantitative or qualified action
    evidence still exists for that seat.

    Deliberate candidate-release replay may reconsider the observation
    after the quantitative blocker is gone.
    """
    observed_seats = set(
        observed_seats
        or []
    )

    unresolved_candidates = set(
        unresolved_candidates
        or []
    )

    preserved_actions = (
        preserved_actions
        or {}
    )

    if seat not in observed_seats:
        return False

    if (
        reconsider_observed_after_candidate_release
    ):
        return False

    return (
        seat in unresolved_candidates
        or seat in preserved_actions
    )


def resolve_silent_boundary_obligations(
    state,
    *,
    canonical,
    tracker,
    street,
    observed_seats=None,
    reconsider_observed_after_candidate_release=False,
):
    """
    Conservatively complete silent old-street obligations at a physically
    confirmed next-street boundary.

    This is a recovery path, not the normal live action path.

    Safety:
    - process owing seats strictly in poker response order;
    - never cross a seat with explicit boundary evidence that failed to
      resolve;
    - never cross unresolved stack evidence;
    - never cross preserved qualified action evidence;
    - facing open aggression, a silent seat with no contrary evidence folds;
    - on an unopened postflop street, a silent seat checks;
    - unopened PREFLOP remains unresolved because blind semantics differ.
    """
    street = str(street or "").upper()
    observed_seats = set(observed_seats or [])

    unresolved_candidates = {
        str(item.get("seat") or "")
        for item in (
            state.get("unresolved_stack_candidates")
            or {}
        ).values()
        if (
            str(item.get("street") or "").upper()
            == street
            and item.get("seat")
        )
    }

    preserved_key = (
        f"{str(state.get('hand_token') or '')}:"
        f"{street}"
    )

    preserved_actions = (
        state.get("preserved_inferred_actions")
        or {}
    ).get(preserved_key) or {}

    resolved = []

    while True:
        status = (
            tracker.commitment_tracker
            .round_status(street)
        )

        owing = list(
            status.get("players_owing_action")
            or []
        )

        if not owing:
            break

        seat = owing[0]

        # An explicit boundary observation that failed to classify an action
        # remains authoritative ambiguity during the ordinary boundary pass.
        #
        # A deliberate post-candidate-removal replay is different: if the
        # quantitative candidate that caused the ambiguity has definitively
        # disappeared, and no qualified quantitative action remains preserved,
        # the observation must not become a permanent veto. The normal betting
        # state below can then determine whether the only remaining passive
        # action is CHECK or FOLD.
        if boundary_observation_must_block_passive_resolution(
            seat=seat,
            observed_seats=observed_seats,
            unresolved_candidates=unresolved_candidates,
            preserved_actions=preserved_actions,
            reconsider_observed_after_candidate_release=(
                reconsider_observed_after_candidate_release
            ),
        ):
            print(
                "[BOUNDARY_PASSIVE_BLOCK] "
                f"street={street} "
                f"seat={seat} "
                "reason=explicit_boundary_observation_with_"
                "surviving_commitment_ownership",
                flush=True,
            )
            break

        if seat in unresolved_candidates:
            print(
                "[BOUNDARY_PASSIVE_BLOCK] "
                f"street={street} "
                f"seat={seat} "
                "reason=unresolved_stack_candidate",
                flush=True,
            )
            break

        if seat in preserved_actions:
            print(
                "[BOUNDARY_PASSIVE_BLOCK] "
                f"street={street} "
                f"seat={seat} "
                "reason=preserved_qualified_action",
                flush=True,
            )
            break

        betting_open = bool(
            status.get("betting_open")
        )

        if betting_open:
            action = "FOLD"
        elif street != "PREFLOP":
            action = "CHECK"
        else:
            print(
                "[BOUNDARY_PASSIVE_BLOCK] "
                f"street={street} "
                f"seat={seat} "
                "reason=unopened_preflop_not_uniquely_resolved",
                flush=True,
            )
            break

        added = canonical.add_boundary_action(
            street=street,
            seat=seat,
            action=action,
            amount_bb=None,
            raise_to_bb=None,
            confidence=0.90,
            source="board_boundary_action_order",
            evidence=[
                "confirmed_next_street",
                "still_owed_action_at_boundary",
                "no_conflicting_commitment_evidence",
            ],
            ts=None,
        )

        if betting_open:
            tracker.commitment_tracker.record_response(
                street,
                seat,
            )
        else:
            tracker.commitment_tracker.consume_pending_action(
                street,
                seat,
            )

        tracker.commitment_tracker.record_action(
            street,
            seat,
        )

        resolved.append(
            {
                "seat": seat,
                "action": action,
                "sequence": added.sequence,
            }
        )

        state = record_timeline(
            state,
            "boundary_passive_action "
            f"{street} {seat} {action}",
        )

        print(
            "[BOUNDARY_PASSIVE_ACTION] "
            f"street={street} "
            f"seat={seat} "
            f"action={action} "
            f"sequence={added.sequence}",
            flush=True,
        )

    return state, resolved


def replay_pending_boundary_results_for_current_street(
    state,
):
    """
    Replay asynchronous boundary results that arrived before their
    matching confirmed next-street board became pending.

    The old street must still be canonical. This closes the ordering
    race:

        boundary result -> deferred
        next-street board -> pending
        deferred boundary result -> old-street reconciliation

    Results for other streets remain preserved.
    """
    pending = list(
        state.get("pending_boundary_results")
        or []
    )

    if not pending:
        return state

    current_street = str(
        state.get("phase")
        or ""
    ).upper()

    expected_next = {
        "PREFLOP": "FLOP",
        "FLOP": "TURN",
        "TURN": "RIVER",
    }.get(current_street)

    if not expected_next:
        return state

    matching_pending_board = any(
        transition_for_board_len(
            len(item.get("board") or [])
        )
        == expected_next
        for item in (
            state.get("pending_board_events")
            or []
        )
        if isinstance(item, dict)
    )

    if not matching_pending_board:
        return state

    ready = []
    remaining = []

    for item in pending:
        item_street = str(
            item.get("street")
            or ""
        ).upper()

        if item_street == current_street:
            ready.append(item)
        else:
            remaining.append(item)

    if not ready:
        return state

    ready.sort(
        key=lambda item: float(
            item.get("ts")
            or 0.0
        )
    )

    state["pending_boundary_results"] = (
        remaining
    )

    print(
        "[BOUNDARY_RESULT_CURRENT_REPLAY] "
        f"street={current_street} "
        f"next={expected_next} "
        f"count={len(ready)}",
        flush=True,
    )

    for item in ready:
        state = handle_boundary_stack_result(
            state,
            item,
        )

    return state


def handle_boundary_stack_result(
    state,
    result,
    *,
    reconsider_observed_after_candidate_release=False,
):
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
        if old_street == current_street:
            # A confirmed next-street board may already be buffered behind
            # unresolved old-street betting obligations. In that state the
            # retrospective boundary result belongs to the street that is
            # still canonical and must be allowed to resolve those obligations
            # BEFORE the board advances.
            pending_boards = list(
                state.get("pending_board_events") or []
            )

            matching_pending_board = any(
                transition_for_board_len(
                    len(item.get("board") or [])
                )
                == expected_current
                for item in pending_boards
                if isinstance(item, dict)
            )

            if matching_pending_board:
                print(
                    "[BOUNDARY_RESULT_CURRENT_STREET] "
                    f"old={old_street} "
                    f"pending_next={expected_current} "
                    f"request={str(result.get('request_id') or '')[:8]}",
                    flush=True,
                )
            else:
                pending = list(
                    state.get("pending_boundary_results") or []
                )

                request_id = str(
                    result.get("request_id") or ""
                )

                already_pending = any(
                    str(item.get("request_id") or "")
                    == request_id
                    for item in pending
                )

                if not already_pending:
                    pending.append(dict(result))
                    pending.sort(
                        key=lambda item: float(
                            item.get("ts") or 0.0
                        )
                    )

                state["pending_boundary_results"] = pending

                print(
                    "[BOUNDARY_RESULT_DEFER] "
                    f"old={old_street} "
                    f"current={current_street} "
                    f"request={request_id[:8]}",
                    flush=True,
                )

                return state
        else:
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

    state = preserve_boundary_evidence(
        state,
        result,
    )

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
    unresolved_observation_seats = set()

    for seat in ordered_seats:
        item = observation_by_seat.get(seat)

        if not isinstance(item, dict):
            continue

        observation = item.get("observation")

        if not isinstance(observation, dict):
            continue

        candidate_key = (
            f"{old_street}:{seat}"
        )

        unresolved_candidate = (
            state.get("unresolved_stack_candidates")
            or {}
        ).get(candidate_key)

        if unresolved_candidate is not None:
            # Boundary evidence is retrospective confirmation. It may not
            # canonicalize a seat while that same seat still owns unresolved
            # quantitative commitment evidence.
            #
            # Mark this explicit observation unresolved as well so the passive
            # boundary recovery path cannot cross it and manufacture a second
            # action.
            unresolved_observation_seats.add(seat)

            print(
                "[BOUNDARY_ACTION_DEFER] "
                f"street={old_street} "
                f"seat={seat} "
                "reason=unresolved_stack_candidate",
                flush=True,
            )

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
            unresolved_observation_seats.add(seat)

            print(
                "[BOUNDARY_UNRESOLVED] "
                f"street={old_street} "
                f"seat={seat} "
                f"reason={promotion.reason}",
                flush=True,
            )

    # A confirmed next-street board is a hard physical boundary. After every
    # available quantitative observation has been consumed, close only those
    # remaining obligations whose passive action is uniquely established by
    # poker order and the absence of conflicting commitment evidence.
    state, passive_resolved = (
        resolve_silent_boundary_obligations(
            state,
            canonical=canonical,
            tracker=tracker,
            street=old_street,
            observed_seats=unresolved_observation_seats,
            reconsider_observed_after_candidate_release=(
                reconsider_observed_after_candidate_release
            ),
        )
    )

    if passive_resolved:
        promoted.extend(passive_resolved)

    if promoted:
        current_street = str(
            canonical.current_street or ""
        ).upper()

        if (
            current_street
            and current_street != old_street
        ):
            eligible_current = [
                seat
                for seat, player
                in canonical.players.items()
                if player.active
                and not player.folded
                and not player.all_in
            ]

            # Preserve already-consumed current-street actions. Historical
            # boundary results may only remove newly ineligible players;
            # they must never rebuild the live action queue.
            canonical.players_to_act = [
                seat
                for seat in canonical.players_to_act
                if seat in eligible_current
            ]

            remaining = (
                tracker.commitment_tracker
                .reconcile_eligible_seats(
                    current_street,
                    eligible_current,
                )
            )

            print(
                "[BOUNDARY_CURRENT_QUEUE_RECONCILE] "
                f"street={current_street} "
                f"remaining={remaining}",
                flush=True,
            )

        # Persist boundary chronology before replay. handle_inferred_action()
        # reloads CanonicalHand, so the newly consumed passive predecessor
        # must already be durable before a deferred quantitative successor
        # is retried.
        canonical_save(canonical)

        # Boundary promotion can expose an already-qualified quantitative
        # action as the new head of poker order. Re-enter that event through
        # the normal inferred-action path immediately; do not wait for an
        # unrelated later event to trigger replay.
        state = replay_pending_inferred_actions(
            state
        )

        # Quantitative replay may have consumed another action, removed its
        # awaiting-action stack candidate, or advanced the betting round.
        # Reload before evaluating old-street completion below.
        canonical = canonical_load()
        tracker = tracker_for_hand(canonical)

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

    if old_status.get("complete"):
        state = clear_preserved_boundary_evidence(
            state,
            hand_token=state.get("hand_token"),
            street=old_street,
        )

    # Keep the public status artifact current-street scoped.
    write_betting_round_status(
        tracker,
        canonical,
        state,
    )

    # Boundary evidence may have consumed the final old-street obligation
    # while a confirmed next-street board was waiting. Release immediately
    # when that made the round complete.
    state = release_pending_board_if_ready(
        state
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

    if t == "stack_candidate_opened":
        return handle_stack_candidate_opened(
            state,
            event,
        )

    if t == "stack_candidate_closed":
        return handle_stack_candidate_closed(
            state,
            event,
        )

    if t == "provisional_bet_opened":
        return handle_provisional_bet_opened(
            state,
            event,
        )

    if t == "provisional_bet_closed":
        return handle_provisional_bet_closed(
            state,
            event,
        )

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

    if t == "actor_observed":
        return handle_actor_observed(state, event)

    if t == "physical_actor_completed":
        return handle_physical_actor_completed(
            state,
            event,
        )

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
            time.sleep(0.02)
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

            # Publish the event-log acknowledgement only after the entire
            # event transaction has completed. This is intentionally owned
            # by the main loop rather than individual handlers.
            if _ACTIVE_TRACKER is not None:
                try:
                    canonical = canonical_load()

                    if (
                        canonical is not None
                        and (
                            canonical.hand_id
                            or "__unknown__"
                        )
                        == _ACTIVE_HAND_ID
                    ):
                        write_betting_round_status(
                            _ACTIVE_TRACKER,
                            canonical,
                            state,
                            processed_event_cursor=i + 1,
                        )
                except Exception as exc:
                    print(
                        "[BETTING_STATUS_ACK_SKIP] "
                        f"cursor={i + 1} "
                        f"reason={type(exc).__name__}: {exc}",
                        flush=True,
                    )

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

        time.sleep(0.02)


if __name__ == "__main__":
    main()
