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


class HeroBootstrap:
    """
    Owns hand initialization after a successful Hero-card read.

    Migration plan
    --------------

    Phase 1 (complete)
        ✓ validate_hero_result()

    Phase 2 (complete)
        ✓ freeze_participants()

    Phase 3
        initialize_hand()

    Future responsibilities:

        dealer detection
        position assignment
        local stack bootstrap
        participant snapshot
        table_context construction
        hero_cards emission
        snapshot_request emission
    """

    @staticmethod
    def initialize_hand(
        *,
        result,
        **kwargs,
    ):
        """
        Begin hand initialization from a completed Hero worker result.

        Current ownership:
            validate Hero worker result

        Remaining responsibilities stay in the coordinator until moved
        here in later, behavior-preserving steps.
        """
        cards, validation_error = validate_hero_result(result)

        return {
            **kwargs,
            "hero_cards": cards,
            "validation_error": validation_error,
        }
