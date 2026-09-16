"""
Single v0.17 current_hand.txt presentation sink.

Input is already-rendered authoritative publication text from
FrameHandObserver. This module has no poker semantic authority.
"""

from pathlib import Path


DEFAULT_CURRENT_HAND = Path(
    "runtime/live/current_hand.txt"
)


def publish_current_hand_text(
    text,
    path=DEFAULT_CURRENT_HAND,
):
    """
    Atomically replace current_hand.txt with one complete observer
    publication.

    The destination can never expose a partially-written projection.
    """
    if not isinstance(text, str):
        raise TypeError(
            "current hand publication must be text"
        )

    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        text,
        encoding="utf-8",
    )

    temporary.replace(path)

    return text
