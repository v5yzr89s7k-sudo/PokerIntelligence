"""
Poker Intelligence
Hero Bootstrap

Purpose
-------
Own all hand-initialization work that begins immediately after a valid
Hero-card read.

This module intentionally contains NO Vision API calls.

Responsibilities (target architecture)
--------------------------------------

Phase 1
    validate Hero result

Phase 2
    freeze participants

Phase 3
    determine dealer

Phase 4
    assign positions

Phase 5
    perform local stack bootstrap

Phase 6
    emit:
        hero_cards
        snapshot_request

The coordinator should eventually reduce to:

    if Hero worker finished:
        HeroBootstrap.initialize_hand(...)

This file is initially documentation only.
Behavior must remain identical while functionality is migrated
incrementally.
"""


def validate_hero_result(result):
    """
    Validate a completed Hero worker result.

    Returns:
        (cards, error)

    cards:
        Two-card list when valid, otherwise None.

    error:
        Stable diagnostic string when invalid, otherwise None.
    """
    if not isinstance(result, dict):
        return None, "result_not_dict"

    if not result.get("ok"):
        return None, (
            "worker_failed:"
            + str(result.get("error") or "unknown")
        )

    cards = result.get("hero_cards") or []

    if len(cards) != 2 or not all(cards):
        return None, f"invalid_cards:{cards!r}"

    return list(cards), None


def freeze_participants(
    participant_collector,
    *,
    hand_token,
    frozen_ts,
):
    """
    Produce the authoritative frozen participant roster.

    This remains a behavior-preserving wrapper while participant
    initialization ownership migrates out of the coordinator.
    """
    return participant_collector.freeze(
        hand_token=hand_token,
        frozen_ts=frozen_ts,
    )
