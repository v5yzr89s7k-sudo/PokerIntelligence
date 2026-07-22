from pathlib import Path
from typing import Iterable
import json
import time


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RECORDS_PATH = (
    ROOT / "runtime/live/participant_validation.jsonl"
)
DEFAULT_SUMMARY_PATH = (
    ROOT / "runtime/live/participant_validation_summary.json"
)


def _ordered_unique(seats: Iterable[str]):
    result = []

    for seat in seats or []:
        seat = str(seat or "").strip()

        if seat and seat not in result:
            result.append(seat)

    return result


def _empty_summary():
    return {
        "hands_compared": 0,
        "exact_matches": 0,
        "mismatches": 0,
        "accuracy_percent": 0.0,
        "local_missing": 0,
        "snapshot_missing": 0,
        "missing_locally_by_seat": {},
        "extra_locally_by_seat": {},
        "recorded_hand_tokens": [],
        "updated_ts": None,
    }


def _load_summary(path):
    path = Path(path)

    if not path.exists():
        return _empty_summary()

    try:
        data = json.loads(path.read_text())
    except Exception:
        return _empty_summary()

    summary = _empty_summary()
    summary.update(data or {})
    return summary


def _write_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True)
    )
    temporary.replace(path)


def record_participant_comparison(
    *,
    hand_token,
    local_dealt_in,
    snapshot_dealt_in,
    local_frame_count=None,
    records_path=DEFAULT_RECORDS_PATH,
    summary_path=DEFAULT_SUMMARY_PATH,
    recorded_ts=None,
):
    records_path = Path(records_path)
    summary_path = Path(summary_path)

    token = str(hand_token or "").strip()

    if not token:
        return {
            "recorded": False,
            "reason": "missing_hand_token",
            "record": None,
            "summary": _load_summary(summary_path),
        }

    local = _ordered_unique(local_dealt_in)
    snapshot = _ordered_unique(snapshot_dealt_in)

    if not local:
        summary = _load_summary(summary_path)

        summary["hands_compared"] = int(
            summary.get("hands_compared") or 0
        ) + 1

        summary["local_missing"] = int(
            summary.get("local_missing") or 0
        ) + 1

        hands = int(summary["hands_compared"])
        matches = int(summary.get("exact_matches") or 0)

        summary["accuracy_percent"] = round(
            matches / hands * 100.0,
            2,
        )

        summary["updated_ts"] = time.time()

        _write_json_atomic(summary_path, summary)

        return {
            "recorded": False,
            "reason": "missing_local_roster",
            "record": None,
            "summary": summary,
        }

    if not snapshot:
        summary = _load_summary(summary_path)

        summary["hands_compared"] = int(
            summary.get("hands_compared") or 0
        ) + 1

        summary["snapshot_missing"] = int(
            summary.get("snapshot_missing") or 0
        ) + 1

        hands = int(summary["hands_compared"])
        matches = int(summary.get("exact_matches") or 0)

        summary["accuracy_percent"] = round(
            matches / hands * 100.0,
            2,
        )

        summary["updated_ts"] = time.time()

        _write_json_atomic(summary_path, summary)

        return {
            "recorded": False,
            "reason": "missing_snapshot_roster",
            "record": None,
            "summary": summary,
        }

    summary = _load_summary(summary_path)
    recorded_tokens = list(
        summary.get("recorded_hand_tokens") or []
    )

    if token in recorded_tokens:
        return {
            "recorded": False,
            "reason": "duplicate_hand_token",
            "record": None,
            "summary": summary,
        }

    local_set = set(local)
    snapshot_set = set(snapshot)

    missing_locally = [
        seat for seat in snapshot
        if seat not in local_set
    ]
    extra_locally = [
        seat for seat in local
        if seat not in snapshot_set
    ]

    exact_match = not missing_locally and not extra_locally

    record = {
        "hand_token": token,
        "recorded_ts": float(recorded_ts or time.time()),
        "local_dealt_in": local,
        "snapshot_dealt_in": snapshot,
        "missing_locally": missing_locally,
        "extra_locally": extra_locally,
        "exact_match": bool(exact_match),
        "local_frame_count": (
            int(local_frame_count)
            if local_frame_count is not None
            else None
        ),
    }

    records_path.parent.mkdir(parents=True, exist_ok=True)

    with records_path.open("a") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")

    summary["hands_compared"] = int(
        summary.get("hands_compared") or 0
    ) + 1

    if exact_match:
        summary["exact_matches"] = int(
            summary.get("exact_matches") or 0
        ) + 1
    else:
        summary["mismatches"] = int(
            summary.get("mismatches") or 0
        ) + 1

    missing_counts = dict(
        summary.get("missing_locally_by_seat") or {}
    )
    extra_counts = dict(
        summary.get("extra_locally_by_seat") or {}
    )

    for seat in missing_locally:
        missing_counts[seat] = int(
            missing_counts.get(seat) or 0
        ) + 1

    for seat in extra_locally:
        extra_counts[seat] = int(
            extra_counts.get(seat) or 0
        ) + 1

    summary["missing_locally_by_seat"] = missing_counts
    summary["extra_locally_by_seat"] = extra_counts

    recorded_tokens.append(token)
    summary["recorded_hand_tokens"] = recorded_tokens[-500:]

    hands = int(summary["hands_compared"])
    matches = int(summary["exact_matches"])

    summary["accuracy_percent"] = round(
        matches / hands * 100.0,
        2,
    )
    summary["updated_ts"] = time.time()

    _write_json_atomic(summary_path, summary)

    return {
        "recorded": True,
        "reason": "recorded",
        "record": record,
        "summary": summary,
    }
