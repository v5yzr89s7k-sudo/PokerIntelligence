from pathlib import Path
from time import perf_counter
from datetime import datetime
import json
import re
import cv2
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.perception_latency import (
    log as log_latency,
    begin as latency_begin,
    end as latency_end,
)
from src.api.position_engine import assign_positions
from src.api.table_snapshot_reader_core_v2 import read_table_snapshot_v2
from src.api.canonical_frame import to_canonical_frame
from src.events.participant_freezer import ParticipantFreezer
from src.api.snapshot_identity_guard import (
    validate_unique_player_identities,
)
from src.events.participant_evidence_store import (
    PARTICIPANT_EVIDENCE_PATH,
    read_evidence,
)

EVENT_LOG = ROOT / "runtime/live/api_events.jsonl"
LATENCY_LOG = ROOT / "runtime/live/snapshot_latency.jsonl"
CAPTURE_DIR = ROOT / "runtime/window_captures"
SNAPSHOT_READER = ROOT / "src/api/table_snapshot_api_reader.py"

CAPTURE_FILENAME_RE = re.compile(
    r"acr_table_(\d{8})_(\d{6})_(\d{6})\.png$"
)


def capture_timestamp(path):
    match = CAPTURE_FILENAME_RE.match(Path(path).name)

    if not match:
        return None

    date_text, time_text, micro_text = match.groups()

    return datetime.strptime(
        date_text + time_text + micro_text,
        "%Y%m%d%H%M%S%f",
    )


def freeze_temporal_participants(target_frame, geometry):
    """
    Reconstruct the immutable starting participant roster from captures
    preceding the Hero-card frame.

    Earlier frames preserve players who folded before the API result arrived.
    Frames after the target are excluded so late table joins cannot enter the
    current hand's participant roster.
    """
    target_frame = Path(target_frame)
    target_ts = capture_timestamp(target_frame)

    if target_ts is None:
        raise ValueError(
            f"could not parse capture timestamp: {target_frame.name}"
        )

    candidates = []

    for candidate in sorted(CAPTURE_DIR.glob("acr_table_*.png")):
        candidate_ts = capture_timestamp(candidate)

        if candidate_ts is None:
            continue

        delta = (candidate_ts - target_ts).total_seconds()

        if -8.0 <= delta <= 0.0:
            candidates.append(candidate)

    if not candidates:
        candidates = [target_frame]

    freezer = ParticipantFreezer()
    freezer.reset(
        started_ts=target_ts.timestamp(),
    )

    for candidate in candidates:
        original = cv2.imread(str(candidate))

        if original is None or original.size == 0:
            continue

        canonical = to_canonical_frame(
            original,
            geometry,
        )

        freezer.observe(
            canonical,
            geometry,
            frame_path=str(candidate),
        )

    diagnostic = freezer.snapshot()

    # A permanent hand roster must not be frozen from a tiny sampling window.
    # When the observer was started after dealing began, early folders may
    # already be absent from every available frame.
    minimum_frames = 6

    if diagnostic["frame_count"] < minimum_frames:
        raise RuntimeError(
            "insufficient hand-start participant evidence: "
            f"frames={diagnostic['frame_count']} "
            f"minimum={minimum_frames}"
        )

    dealt_in_seats = freezer.freeze(
        hero_is_dealt=True,
        frozen_ts=target_ts.timestamp(),
    )

    diagnostic = freezer.snapshot()

    print(
        f"[PARTICIPANT_FREEZE] "
        f"frames={diagnostic['frame_count']} "
        f"seats={dealt_in_seats}",
        flush=True,
    )

    for seat, scores in diagnostic["max_scores"].items():
        print(
            f"[PARTICIPANT_EVIDENCE] "
            f"seat={seat} "
            f"card_1={scores['card_1']:.3f} "
            f"card_2={scores['card_2']:.3f} "
            f"dealt_in={seat in dealt_in_seats}",
            flush=True,
        )

    return dealt_in_seats, diagnostic


def latest_capture():
    files = sorted(CAPTURE_DIR.glob("acr_table_*.png"))
    return files[-1] if files else None


def emit(event):
    event["ts"] = time.time()
    with EVENT_LOG.open("a") as f:
        f.write(json.dumps(event) + "\n")
        f.flush()


def run_snapshot(frame, dealt_in_seats=None):
    t0 = perf_counter()

    try:
        snapshot, timings = read_table_snapshot_v2(
            frame,
            dealt_in_seats=dealt_in_seats,
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - t0) * 1000.0

        print(
            f"[SNAPSHOT] in-process reader failed: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            f"[PROFILE] SNAPSHOT_WORKER "
            f"total={elapsed_ms:.1f}ms failed=true",
            flush=True,
        )

        return None, elapsed_ms

    elapsed_ms = (perf_counter() - t0) * 1000.0

    print(
        f"[PROFILE] SNAPSHOT_WORKER "
        f"total={elapsed_ms:.1f}ms "
        f"prepare={timings['prepare_ms']:.1f}ms "
        f"payload={timings['payload_ms']:.1f}ms "
        f"api={timings['api_ms']:.1f}ms "
        f"parse={timings['parse_ms']:.1f}ms "
        f"primary_api={timings['primary_api_ms']:.1f}ms "
        f"primary_parse={timings['primary_parse_ms']:.1f}ms "
        f"retry_build={timings['retry_build_ms']:.1f}ms "
        f"retry_api={timings['retry_api_ms']:.1f}ms "
        f"retry_parse={timings['retry_parse_ms']:.1f}ms "
        f"retry_count={timings['retry_count']} "
        f"retry_kb={timings['retry_image_bytes'] / 1024:.1f} "
        f"images={timings['image_count']} "
        f"dealer={timings['dealer_ms']:.1f}ms "
        f"seat_cards={timings['seat_card_count']} "
        f"image_kb={timings['image_bytes'] / 1024:.1f}",
        flush=True,
    )

    record = {
        "ts": time.time(),
        "total_ms": round(elapsed_ms, 1),
        "primary_api_ms": round(timings["primary_api_ms"], 1),
        "retry_api_ms": round(timings["retry_api_ms"], 1),
        "images": timings["image_count"],
        "cached": 8 - timings["image_count"],
        "changed": timings["image_count"],
        "image_kb": round(
            timings["image_bytes"] / 1024,
            1,
        ),
        "retry_count": timings["retry_count"],
    }

    with LATENCY_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")

    return snapshot, elapsed_ms


def process_event(event, processed_hero_events):
    if event.get("type") != "snapshot_request":
        return

    print("[SNAPSHOT_TRIGGER] snapshot_request received", flush=True)

    event_ts = event.get("ts")
    event_key = str(event_ts)

    if event_key in processed_hero_events:
        return

    processed_hero_events.add(event_key)

    request_id = event.get("source_request_id") or f"snapshot-{event_key}"
    hand_token = event.get("hand_token")

    log_latency(
        "trigger_consumed",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        trigger_event="hero_cards",
        trigger_ts=event_ts,
    )

    frame = None

    frame_text = event.get("canonical_frame")

    if frame_text:
        candidate = Path(frame_text)
        if candidate.exists():
            frame = candidate
        else:
            print(
                f"[SNAPSHOT] canonical frame missing: {candidate}",
                flush=True,
            )

    if frame is None:
        print(
            "[SNAPSHOT] hero_cards event has no usable canonical frame",
            flush=True,
        )
        return

    print(f"[SNAPSHOT] reading from {frame.name}", flush=True)

    log_latency(
        "worker_started",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        frame=str(frame),
    )

    latency_begin(
        request_id,
        "snapshot_pipeline",
        hand_token=hand_token,
    )

    geometry = json.loads(
        (ROOT / "config/geometry.json").read_text()
    )

    expected_token = str(
        event.get("hand_token") or ""
    )

    # Keep table occupancy and hand participation separate.
    #
    # roster_seats:
    #     every occupied starting seat that snapshot enrichment should read.
    #
    # dealt_in_seats:
    #     only players actually dealt cards in this hand; these seats own
    #     poker positions, blinds, betting order, and action chronology.
    requested_roster_seats = list(
        event.get("roster_seats") or []
    )

    requested_dealt_in_seats = list(
        event.get("dealt_in_seats") or []
    )

    if requested_roster_seats:
        roster_seats = list(
            dict.fromkeys(
                requested_roster_seats
            )
        )

        dealt_in_seats = list(
            dict.fromkeys(
                requested_dealt_in_seats
                or requested_roster_seats
            )
        )

        participant_diagnostic = {
            "source": "canonical_starting_roster",
            "hand_token": hand_token,
            "frame_count": None,
            "roster_seats": list(roster_seats),
            "dealt_in_seats": list(dealt_in_seats),
        }

        print(
            "[PARTICIPANT_FREEZE] "
            "source=canonical_starting_roster "
            f"roster={roster_seats} "
            f"dealt={dealt_in_seats}",
            flush=True,
        )

    else:
        # Backward-compatible fallback for callers that do not yet provide
        # the explicit roster/dealt-in split.
        shared_evidence = read_evidence(
            PARTICIPANT_EVIDENCE_PATH
        )

        shared_token = str(
            shared_evidence.get("hand_token") or ""
        )
        expected_token = str(hand_token or "")

        if (
            shared_token
            and shared_token == expected_token
            and int(shared_evidence.get("frame_count") or 0) >= 6
        ):
            freezer = ParticipantFreezer.from_evidence(
                shared_evidence
            )

            dealt_in_seats = freezer.freeze(
                hero_is_dealt=True,
                frozen_ts=event_ts or time.time(),
            )
            participant_diagnostic = freezer.snapshot()

            print(
                f"[PARTICIPANT_FREEZE] source=shared "
                f"frames={participant_diagnostic['frame_count']} "
                f"seats={dealt_in_seats}",
                flush=True,
            )
        else:
            try:
                dealt_in_seats, participant_diagnostic = (
                    freeze_temporal_participants(
                        frame,
                        geometry,
                    )
                )

                print(
                    "[PARTICIPANT_FREEZE] source=historical",
                    flush=True,
                )

            except Exception as exc:
                print(
                    f"[PARTICIPANT_FREEZE] failed "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

                dealt_in_seats = []

                participant_diagnostic = {
                    "error": str(exc),
                    "shared_hand_token": shared_token,
                    "expected_hand_token": expected_token,
                    "shared_frame_count": int(
                        shared_evidence.get("frame_count") or 0
                    ),
                }

        roster_seats = list(
            dealt_in_seats
        )

    print(
        "[PARTICIPANTS] "
        f"roster_count={len(roster_seats)} "
        f"roster={roster_seats} "
        f"dealt_count={len(dealt_in_seats)} "
        f"dealt={dealt_in_seats}",
        flush=True,
    )


    # Snapshot enrichment reads every occupied starting seat so the TABLE
    # section receives all seated players in one atomic result.
    snapshot, elapsed_ms = run_snapshot(
        frame,
        dealt_in_seats=roster_seats,
    )

    if snapshot:
        # V2 used roster_seats only as its read inventory. Restore the actual
        # hand participants before any poker semantics are calculated.
        snapshot["roster_seats"] = list(
            roster_seats
        )
        snapshot["dealt_in_seats"] = list(
            dealt_in_seats
        )
        snapshot["participant_diagnostic"] = (
            participant_diagnostic
        )

    if not snapshot:
        latency_end(
            request_id,
            "snapshot_pipeline",
            hand_token=hand_token,
            ok=False,
            elapsed_ms=elapsed_ms,
        )

        log_latency(
            "worker_finished",
            request_id=request_id,
            worker="snapshot",
            hand_token=hand_token,
            ok=False,
            elapsed_ms=elapsed_ms,
        )
        return

    players = snapshot.get("players") or []

    # Seat identities are immutable within one snapshot. Never compensate
    # for a missing dealt-in seat by reusing another player's record.
    seen_names = {}
    duplicate_identities = []

    for player in players:
        if not isinstance(player, dict):
            continue

        seat = str(player.get("seat") or "")
        name = str(player.get("name") or "").strip()

        if not seat or not name:
            continue

        prior_seat = seen_names.get(name)

        if prior_seat and prior_seat != seat:
            duplicate_identities.append({
                "name": name,
                "first_seat": prior_seat,
                "duplicate_seat": seat,
            })
        else:
            seen_names[name] = seat

    if duplicate_identities:
        print(
            "[SNAPSHOT_WARNING] "
            "duplicated player identity across seats: "
            f"{duplicate_identities}",
            flush=True,
        )

        # Keep the first occurrence of a player identity and blank later
        # duplicates instead of aborting the entire snapshot.
        seen = set()

        for player in players:
            name = str(player.get("name") or "").strip()

            if not name:
                continue

            if name in seen:
                player["name"] = ""
                player["identity_conflict"] = True
                continue

            seen.add(name)

    # A missing dealt-in seat must remain missing. Never compensate by
    # reusing or copying another player's identity into that seat.
    validate_unique_player_identities(players)

    dealt_in = set(
        snapshot.get("dealt_in_seats") or []
    )

    hand_players = [
        player
        for player in players
        if player.get("seat") in dealt_in
    ]

    dealer_button_seat = (
        snapshot.get("dealer_button_seat")
        or ""
    )

    positions = assign_positions(
        hand_players,
        dealer_button_seat,
    )

    print(
        f"[POSITIONS] seated={len(players)} "
        f"hand={len(hand_players)} "
        f"hero={positions.get('hero')}",
        flush=True,
    )

    hero_position = (
        positions.get("hero")
        or "unknown"
    )

    print("\n================ SNAPSHOT PLAYER DUMP ================", flush=True)
    for player in players:
        print(
            f"{player.get('seat'):18} "
            f"name={repr(player.get('name')):24} "
            f"stack={repr(player.get('stack_text')):12} "
            f"hero={player.get('is_hero')}",
            flush=True,
        )

    print(
        f"occupied_seats={snapshot.get('occupied_seats')}",
        flush=True,
    )
    print(
        f"dealt_in_seats={snapshot.get('dealt_in_seats')}",
        flush=True,
    )
    print(
        f"participant_count={len(snapshot.get('dealt_in_seats') or [])}",
        flush=True,
    )
    print(
        f"snapshot_count={len(players)}",
        flush=True,
    )
    print("=====================================================\n", flush=True)

    latency_end(
        request_id,
        "snapshot_pipeline",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=elapsed_ms,
        player_count=len(players),
    )

    log_latency(
        "worker_finished",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        ok=True,
        elapsed_ms=elapsed_ms,
        player_count=len(players),
    )

    emit({
        "type": "table_snapshot",
        "players": players,
        "dealer_button_seat": dealer_button_seat,
        "positions": positions,
        "hero_position": hero_position,
        "dealt_in_seats": list(
            snapshot.get("dealt_in_seats") or []
        ),
        "confidence": snapshot.get("confidence"),
        "source_request_id": request_id,
        "hand_token": hand_token,
    })

    log_latency(
        "event_emitted",
        request_id=request_id,
        worker="snapshot",
        hand_token=hand_token,
        event_type="table_snapshot",
        player_count=len(players),
    )

    print("[SNAPSHOT] emitted table_snapshot", flush=True)


def main():
    print("api_snapshot_worker running. Ctrl+C to stop.", flush=True)

    offset = 0
    processed_hero_events = set()

    while True:
        if not EVENT_LOG.exists():
            offset = 0
            time.sleep(0.1)
            continue

        size = EVENT_LOG.stat().st_size

        # Runner resets/truncates runtime files at startup.
        if size < offset:
            offset = 0
            processed_hero_events.clear()

        if size == offset:
            time.sleep(0.1)
            continue

        with EVENT_LOG.open("r") as f:
            f.seek(offset)

            while True:
                line_start = f.tell()
                line = f.readline()

                if not line:
                    break

                # Do not consume a partially written JSONL record.
                if not line.endswith("\n"):
                    f.seek(line_start)
                    break

                offset = f.tell()

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print("[SNAPSHOT] ignored invalid event JSON", flush=True)
                    continue

                process_event(event, processed_hero_events)


if __name__ == "__main__":
    main()
