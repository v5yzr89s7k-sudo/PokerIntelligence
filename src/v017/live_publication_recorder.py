"""
Append-only diagnostic recorder for authoritative live publications.

This module has no poker-semantic or publication authority.

It records only publications that have already crossed the
current_hand.txt sink boundary.
"""

import json
from pathlib import Path


DEFAULT_PATH = Path(
    "runtime/live/v017_publication_progression.jsonl"
)


def reset_publication_progression(
    path=DEFAULT_PATH,
):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "",
        encoding="utf-8",
    )


def record_publication(
    publication,
    sink_complete_ns,
    path=DEFAULT_PATH,
):
    if not isinstance(publication, dict):
        raise TypeError(
            "publication must be a dict"
        )

    text = publication.get("text")

    if not isinstance(text, str):
        raise TypeError(
            "publication text must be str"
        )

    record = {
        "frame": publication.get("frame"),
        "street": publication.get("street"),
        "action_count":
            publication.get("action_count"),
        "next_actor":
            publication.get("next_actor"),
        "sink_complete_ns": int(
            sink_complete_ns
        ),
        "text": text,
    }

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        handle.write("\n")

    return record
