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

from src.api.position_engine import assign_positions
from src.vision.dealer_detector import detect_dealer_button


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
        participant_collector,
        hand_token,
        frozen_ts,
    ):
        """
        Begin hand initialization from a completed Hero worker result.

        Current ownership:
            validate Hero worker result
            freeze participants
            detect dealer
            assign positions
        """
        cards, validation_error = validate_hero_result(result)

        if validation_error:
            return {
                "hand_token": hand_token,
                "hero_cards": None,
                "validation_error": validation_error,
                "frozen_participants": [],
                "dealer": None,
                "positions": {},
            }

        frozen_participants = freeze_participants(
            participant_collector,
            hand_token=hand_token,
            frozen_ts=frozen_ts,
        )

        dealer = detect_dealer_button(
            result["canonical_frame"]
        )

        position_players = [
            {"seat": seat}
            for seat in frozen_participants
        ]

        positions = assign_positions(
            position_players,
            dealer["dealer_button_seat"],
        )

        return {
            "hand_token": hand_token,
            "hero_cards": cards,
            "validation_error": None,
            "frozen_participants": frozen_participants,
            "dealer": dealer,
            "positions": positions,
        }
