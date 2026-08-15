from dataclasses import dataclass, asdict
from typing import Optional

from src.state.boundary_stack_observation import (
    BoundaryStackObservation,
)
from src.state.boundary_action_resolver import (
    resolve_boundary_action,
)


@dataclass(frozen=True)
class BoundaryPromotionResult:
    street: str
    seat: str
    resolved: bool
    action: Optional[str]
    reason: str
    canonical_sequence: Optional[int] = None

    def to_dict(self):
        return asdict(self)


def promote_boundary_observation(
    *,
    hand,
    commitment_tracker,
    street,
    seat,
    observation,
):
    """
    Promote one trusted retrospective stack observation.

    This function owns no OCR and performs no guessing.

    Safety contract:
    - seat must still owe action on the preserved old street;
    - first integration supports resolved aggression only;
    - resolver must uniquely establish FOLD/CALL/CHECK;
    - canonical promotion uses the explicit historical-street primitive;
    - old-street response obligation is consumed only after promotion.
    """
    street = str(street or "").upper()
    seat = str(seat or "")

    if not street or not seat:
        return BoundaryPromotionResult(
            street=street,
            seat=seat,
            resolved=False,
            action=None,
            reason="missing street or seat",
        )

    status = commitment_tracker.round_status(street)

    owing = list(
        status.get("players_owing_action") or []
    )

    if seat not in owing:
        return BoundaryPromotionResult(
            street=street,
            seat=seat,
            resolved=False,
            action=None,
            reason="player does not owe action on preserved street state",
        )

    # Unopened PREFLOP reconciliation remains intentionally unsupported
    # because blind-specific semantics cannot be resolved from an unchanged
    # boundary stack alone. Postflop unopened streets may proceed to the
    # existing boundary resolver, which can resolve an owing player with a
    # trusted unchanged stack as CHECK.
    if (
        not status.get("betting_open")
        and street == "PREFLOP"
    ):
        return BoundaryPromotionResult(
            street=street,
            seat=seat,
            resolved=False,
            action=None,
            reason="unopened preflop boundary promotion not supported",
        )

    player = hand.players.get(seat)

    if player is None:
        return BoundaryPromotionResult(
            street=street,
            seat=seat,
            resolved=False,
            action=None,
            reason="unknown canonical player",
        )

    observed_stack = observation.get("stack_bb")

    boundary = BoundaryStackObservation(
        street=street,
        seat=seat,
        previous_stack_bb=player.last_confirmed_stack_bb,
        observed_stack_bb=observed_stack,
        confidence=float(
            observation.get("confidence") or 0.0
        ),
        votes=int(
            observation.get("votes") or 0
        ),
        mode=str(
            observation.get("mode") or ""
        ),
        frame_path=str(
            observation.get("frame_path") or ""
        ),
        ts=observation.get("frame_ts"),
    )

    ante = hand.ante_committed_bb(
        seat,
        street,
    )

    prior_total = float(
        player.committed_by_street.get(
            street,
            0.0,
        )
        or 0.0
    )

    prior_live = round(
        max(0.0, prior_total - ante),
        4,
    )

    resolution = resolve_boundary_action(
        boundary,
        owes_action=True,
        betting_open=bool(
            status.get("betting_open")
        ),
        current_price_bb=float(
            status.get("current_price") or 0.0
        ),
        prior_live_commitment_bb=prior_live,
    )

    if not resolution.resolved:
        return BoundaryPromotionResult(
            street=street,
            seat=seat,
            resolved=False,
            action=None,
            reason=resolution.reason,
        )

    action = hand.add_boundary_action(
        street=street,
        seat=seat,
        action=resolution.action,
        amount_bb=resolution.amount_bb,
        raise_to_bb=resolution.raise_to_bb,
        confidence=resolution.confidence,
        source="boundary_stack_resolution",
        evidence=[
            "trusted_terminal_stack",
            "preserved_action_obligation",
            observation.get("mode") or "unknown_stack_read",
        ],
        ts=observation.get("frame_ts"),
    )

    if status.get("betting_open"):
        commitment_tracker.record_response(
            street,
            seat,
        )
    else:
        commitment_tracker.consume_pending_action(
            street,
            seat,
        )

    commitment_tracker.record_action(
        street,
        seat,
    )

    return BoundaryPromotionResult(
        street=street,
        seat=seat,
        resolved=True,
        action=action.action,
        reason=resolution.reason,
        canonical_sequence=action.sequence,
    )
