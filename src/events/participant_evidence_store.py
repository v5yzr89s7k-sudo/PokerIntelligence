from pathlib import Path
import json
import os
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PARTICIPANT_EVIDENCE_PATH = (
    ROOT / "runtime/live/participant_evidence.json"
)


def empty_evidence():
    return {
        "hand_token": "",
        "started_ts": None,
        "updated_ts": None,
        "frame_count": 0,
        "frozen": False,
        "dealt_in_seats": [],
        "threshold": 0.0,
        "max_scores": {},
        "max_frames": {},
    }


def read_evidence(path):
    path = Path(path)

    if not path.exists():
        return empty_evidence()

    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return empty_evidence()

    result = empty_evidence()
    result.update(data or {})
    return result


def write_evidence(path, evidence):
    """
    Atomically publish participant evidence so another process never reads
    a partially written JSON document.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        evidence,
        indent=2,
        sort_keys=True,
    ) + "\n"

    fd, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )

    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def reset_evidence(path, hand_token="", started_ts=None):
    evidence = empty_evidence()
    evidence["hand_token"] = str(hand_token or "")
    evidence["started_ts"] = started_ts
    write_evidence(path, evidence)
    return evidence
