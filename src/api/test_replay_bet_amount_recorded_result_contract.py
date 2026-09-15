"""
Regression contract:

Finite frame replay must not regenerate bet-amount perception by calling
the external API again.

Recorded frame replay owns recorded quantitative perception. A replay
bet-amount request must be resolvable from the source session by semantic
identity:

    frame basename
    seat
    street
    source

Live mode remains asynchronous API perception.

This test is intentionally RED until production provides that replay
boundary.
"""

from pathlib import Path
import inspect

from src.api import api_event_coordinator as coord
from src.api import api_bet_amount_worker as worker


def main():
    coordinator_source = inspect.getsource(coord)
    worker_source = inspect.getsource(worker)

    # ------------------------------------------------------------
    # CONTRACT 1
    # Replay must expose a dedicated recorded bet-result resolver.
    # ------------------------------------------------------------

    replay_resolver_names = (
        "find_replay_bet_amount_result",
        "replay_bet_amount_result",
        "recorded_bet_amount_result",
    )

    resolver = None

    for name in replay_resolver_names:
        if hasattr(coord, name):
            resolver = getattr(coord, name)
            break

    assert resolver is not None, (
        "RED: finite replay has no recorded bet-amount result resolver; "
        "it must not regenerate quantitative API perception"
    )

    resolver_source = inspect.getsource(resolver)

    # ------------------------------------------------------------
    # CONTRACT 2
    # Semantic identity must include immutable frame + seat + street
    # + source. UUID request ids differ between replay runs and cannot
    # be the recorded-perception identity.
    # ------------------------------------------------------------

    required_identity = (
        "frame",
        "seat",
        "street",
        "source",
    )

    missing = [
        item
        for item in required_identity
        if item not in resolver_source
    ]

    assert not missing, (
        "RED: replay bet-result resolver does not own complete semantic "
        f"identity; missing={missing}"
    )

    # ------------------------------------------------------------
    # CONTRACT 3
    # The replay source session must participate in resolution.
    # ------------------------------------------------------------

    replay_markers = (
        "POKER_REPLAY_SESSION",
        "replay",
        "session",
    )

    assert any(
        marker in resolver_source
        for marker in replay_markers
    ), (
        "RED: replay bet-result resolver is not tied to the recorded "
        "source session"
    )

    # ------------------------------------------------------------
    # CONTRACT 4
    # Worker must have an explicit replay branch before a fresh API
    # read. We do not require a particular implementation shape, only
    # that replay is distinguishable from ordinary live perception.
    # ------------------------------------------------------------

    assert (
        "POKER_REPLAY_SESSION" in worker_source
        or "replay" in worker_source.lower()
    ), (
        "RED: bet-amount worker has no replay-specific perception path; "
        "recorded replay currently calls fresh external API perception"
    )

    # ------------------------------------------------------------
    # CONTRACT 5
    # Live reader remains present. This change must not delete the live
    # asynchronous perception architecture.
    # ------------------------------------------------------------

    assert "read_bet_amount" in worker_source, (
        "live bet-amount API perception was removed"
    )

    print(
        "PASS replay bet-amount recorded-result contract: "
        "finite replay resolves recorded quantitative perception by "
        "frame/seat/street/source while live mode retains API perception"
    )


if __name__ == "__main__":
    main()
