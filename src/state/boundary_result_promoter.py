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


def resolve_boundary_observation(
    *,
    hand,
    commitment_tracker,
    street,
    seat,
    observation,
):
    """
    Resolve one trusted retrospective stack observation without mutation.

    This adapter prepares preserved betting/canonical context for the pure
    boundary-action resolver. It does not mutate CanonicalHand or
    StreetCommitmentTracker and has no action-authoring authority.
    """
    street = str(street or "").upper()
    seat = str(seat or "")

    if not street or not seat:
        from src.state.boundary_action_resolver import (
            BoundaryActionResolution,
        )

        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="missing street or seat",
        )

    status = commitment_tracker.round_status(
        street
    )

    owing = list(
        status.get("players_owing_action")
        or []
    )

    if seat not in owing:
        from src.state.boundary_action_resolver import (
            BoundaryActionResolution,
        )

        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason=(
                "player does not owe action on "
                "preserved street state"
            ),
        )

    # Preserve the existing boundary policy:
    # unchanged PREFLOP evidence without open aggression cannot uniquely
    # establish blind-specific semantics. Postflop unopened traversal may
    # still resolve CHECK through the pure resolver.
    if (
        not status.get("betting_open")
        and street == "PREFLOP"
    ):
        from src.state.boundary_action_resolver import (
            BoundaryActionResolution,
        )

        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason=(
                "unopened preflop boundary "
                "promotion not supported"
            ),
        )

    player = hand.players.get(seat)

    if player is None:
        from src.state.boundary_action_resolver import (
            BoundaryActionResolution,
        )

        return BoundaryActionResolution(
            street=street,
            seat=seat,
            action=None,
            resolved=False,
            reason="unknown canonical player",
        )

    observed_stack = observation.get(
        "stack_bb"
    )

    boundary = BoundaryStackObservation(
        street=street,
        seat=seat,
        previous_stack_bb=(
            player.last_confirmed_stack_bb
        ),
        observed_stack_bb=observed_stack,
        confidence=float(
            observation.get("confidence")
            or 0.0
        ),
        votes=int(
            observation.get("votes")
            or 0
        ),
        mode=str(
            observation.get("mode")
            or ""
        ),
        frame_path=str(
            observation.get("frame_path")
            or ""
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
        max(
            0.0,
            prior_total - ante,
        ),
        4,
    )

    return resolve_boundary_action(
        boundary,
        owes_action=True,
        betting_open=bool(
            status.get("betting_open")
        ),
        current_price_bb=float(
            status.get("current_price")
            or 0.0
        ),
        prior_live_commitment_bb=(
            prior_live
        ),
    )
