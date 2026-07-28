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


def bootstrap_local_stacks(
    *,
    canonical_image,
    frozen_participants,
    geometry,
    crop_geometry_region,
    stack_reader,
):
    """
    Build the initial local player list from stack OCR.

    Returns:
        local_players
    """
    local_players = []

    for seat in frozen_participants:
        stack_result = {
            "stack_bb": None,
            "stack_text": "",
            "confidence": 0.0,
            "mode": "unavailable",
        }

        region = (
            (geometry.get("stack_regions") or {})
            .get(seat)
        )

        if canonical_image is not None and region:
            stack_crop = crop_geometry_region(
                canonical_image,
                region,
            )

            if stack_crop is not None and stack_crop.size:
                try:
                    stack_result = stack_reader(stack_crop)
                except Exception as exc:
                    print(
                        f"[LOCAL_STACK] seat={seat} "
                        f"failed={type(exc).__name__}: {exc}",
                        flush=True,
                    )

        stack_bb = stack_result.get("stack_bb")
        confidence = float(
            stack_result.get("confidence") or 0.0
        )
        votes = int(
            stack_result.get("votes") or 0
        )

        trusted = (
            stack_bb is not None
            and float(stack_bb) > 0.0
            and confidence >= 0.95
            and votes >= 2
        )

        local_players.append({
            "seat": seat,
            "name": "",
            "stack_bb": (
                float(stack_bb)
                if trusted
                else None
            ),
            "stack_text": (
                str(stack_result.get("stack_text") or "")
                if trusted
                else ""
            ),
            "stack_confidence": confidence,
            "stack_read_mode": stack_result.get(
                "mode",
                "unknown",
            ),
            "is_hero": seat == "hero",
            "is_active": True,
        })

        print(
            f"[LOCAL_STACK] seat={seat} "
            f"stack={stack_bb if trusted else None} "
            f"confidence={confidence:.2f} "
            f"votes={votes} "
            f"trusted={trusted}",
            flush=True,
        )

    return local_players
