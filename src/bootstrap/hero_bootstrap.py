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

import time

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
        total_started = time.perf_counter()

        stage_started = time.perf_counter()
        cards, validation_error = validate_hero_result(result)
        validation_ms = (
            time.perf_counter() - stage_started
        ) * 1000.0

        if validation_error:
            total_ms = (
                time.perf_counter() - total_started
            ) * 1000.0

            return {
                "hand_token": hand_token,
                "hero_cards": None,
                "validation_error": validation_error,
                "frozen_participants": [],
                "dealer": None,
                "positions": {},
                "timings_ms": {
                    "validation": validation_ms,
                    "participant_freeze": 0.0,
                    "dealer_detection": 0.0,
                    "position_assignment": 0.0,
                    "total": total_ms,
                },
            }

        stage_started = time.perf_counter()
        frozen_participants = freeze_participants(
            participant_collector,
            hand_token=hand_token,
            frozen_ts=frozen_ts,
        )
        participant_freeze_ms = (
            time.perf_counter() - stage_started
        ) * 1000.0

        stage_started = time.perf_counter()
        dealer = detect_dealer_button(
            result["canonical_frame"]
        )
        dealer_detection_ms = (
            time.perf_counter() - stage_started
        ) * 1000.0

        position_players = [
            {"seat": seat}
            for seat in frozen_participants
        ]

        stage_started = time.perf_counter()
        positions = assign_positions(
            position_players,
            dealer["dealer_button_seat"],
        )
        position_assignment_ms = (
            time.perf_counter() - stage_started
        ) * 1000.0

        total_ms = (
            time.perf_counter() - total_started
        ) * 1000.0

        return {
            "hand_token": hand_token,
            "hero_cards": cards,
            "validation_error": None,
            "frozen_participants": frozen_participants,
            "dealer": dealer,
            "positions": positions,
            "timings_ms": {
                "validation": validation_ms,
                "participant_freeze": participant_freeze_ms,
                "dealer_detection": dealer_detection_ms,
                "position_assignment": position_assignment_ms,
                "total": total_ms,
            },
        }


def build_local_players(*, frozen_participants):
    """
    Build the initial local player records without performing OCR.
    """
    return [
        {
            "seat": seat,
            "name": "",
            "stack_bb": None,
            "stack_text": "",
            "stack_confidence": 0.0,
            "stack_read_mode": "unavailable",
            "is_hero": seat == "hero",
            "is_active": True,
        }
        for seat in frozen_participants
    ]


def populate_local_stacks(
    *,
    local_players,
    canonical_image,
    geometry,
    crop_geometry_region,
    stack_reader,
):
    """
    Populate existing local player records using stack OCR.
    """
    total_started = time.perf_counter()

    players_by_seat = {
        player["seat"]: player
        for player in local_players
    }

    for seat, player in players_by_seat.items():
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

        player.update({
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
        })

        print(
            f"[LOCAL_STACK] seat={seat} "
            f"stack={stack_bb if trusted else None} "
            f"confidence={confidence:.2f} "
            f"votes={votes} "
            f"trusted={trusted}",
            flush=True,
        )

    total_ms = (
        time.perf_counter() - total_started
    ) * 1000.0

    print(
        "[LATENCY_WATERFALL] "
        f"local_stack_bootstrap={total_ms:.1f}ms "
        f"seats={len(local_players)}",
        flush=True,
    )

    return local_players


def bootstrap_local_stacks(
    *,
    canonical_image,
    frozen_participants,
    geometry,
    crop_geometry_region,
    stack_reader,
):
    """
    Preserve the existing stack-bootstrap behavior through the split API.
    """
    local_players = build_local_players(
        frozen_participants=frozen_participants,
    )

    return populate_local_stacks(
        local_players=local_players,
        canonical_image=canonical_image,
        geometry=geometry,
        crop_geometry_region=crop_geometry_region,
        stack_reader=stack_reader,
    )
