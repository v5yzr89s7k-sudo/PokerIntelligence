from dataclasses import dataclass, asdict
from typing import List


@dataclass(frozen=True)
class PreservedActionReconciliation:
    resolved: bool
    actions: List[dict]
    reason: str

    def to_dict(self):
        return asdict(self)


def reconcile_preserved_actions(
    *,
    hand,
    commitment_tracker,
    street,
    qualified_actions,
):
    """
    Build a chronological historical action sequence from already-qualified
    action evidence.

    This function does not mutate CanonicalHand.

    Safety:
    - only PREFLOP is supported initially;
    - every skipped seat with commitment evidence must have its own qualified
      action before reconciliation can proceed;
    - seats with no commitment evidence may resolve as FOLD;
    - CALL/RAISE semantics require quantitative commitment sizing;
    - result order follows immutable poker street order, never event arrival.
    """
    street = str(street or "").upper()

    if street != "PREFLOP":
        return PreservedActionReconciliation(
            False,
            [],
            "only PREFLOP preserved reconciliation is supported",
        )

    state = commitment_tracker._state(street)
    order = list(state.street_order or [])

    if not order:
        return PreservedActionReconciliation(
            False,
            [],
            "street order unavailable",
        )

    by_seat = {
        str(seat): dict(event)
        for seat, event in (qualified_actions or {}).items()
        if seat and isinstance(event, dict)
    }

    committed = set(
        commitment_tracker.committed_players(street)
    )

    if not by_seat:
        return PreservedActionReconciliation(
            False,
            [],
            "no qualified actions",
        )

    # We only need to reconstruct through the latest qualified actor.
    indices = [
        order.index(seat)
        for seat in by_seat
        if seat in order
    ]

    if not indices:
        return PreservedActionReconciliation(
            False,
            [],
            "qualified actors are outside street order",
        )

    last_index = max(indices)
    traversal = order[:last_index + 1]

    actions = []
    live_price = 1.0

    for seat in traversal:
        event = by_seat.get(seat)

        if event is None:
            if seat in committed:
                return PreservedActionReconciliation(
                    False,
                    [],
                    (
                        "committed seat still lacks qualified action: "
                        f"{seat}"
                    ),
                )

            actions.append({
                "seat": seat,
                "action": "FOLD",
                "amount_bb": None,
                "raise_to_bb": None,
                "confidence": 0.98,
                "source": "preserved_preflop_reconciliation",
                "evidence": ["no_commitment_evidence"],
                "ts": None,
            })
            continue

        raw = str(event.get("action") or "").upper()

        measurements = event.get("measurements") or {}
        stack_change = measurements.get("stack_change") or {}

        delta = event.get("delta_bb")

        if delta is None:
            delta = stack_change.get("delta_bb")

        try:
            delta = (
                None
                if delta is None
                else round(float(delta), 2)
            )
        except (TypeError, ValueError):
            delta = None

        player = hand.players.get(seat)

        if player is None:
            return PreservedActionReconciliation(
                False,
                [],
                f"unknown canonical player: {seat}",
            )

        prior_total = float(
            player.committed_by_street.get(
                street,
                0.0,
            )
            or 0.0
        )

        ante = float(
            hand.ante_committed_bb(
                seat,
                street,
            )
            or 0.0
        )

        prior_live = max(
            0.0,
            prior_total - ante,
        )

        if raw == "CALL":
            if delta is None:
                return PreservedActionReconciliation(
                    False,
                    [],
                    f"CALL lacks sizing for {seat}",
                )

            canonical = "CALL"
            amount_bb = delta
            raise_to_bb = None

        elif raw in {
            "CALL_OR_RAISE",
            "BET_OR_RAISE",
        }:
            if delta is None:
                return PreservedActionReconciliation(
                    False,
                    [],
                    f"{raw} lacks sizing for {seat}",
                )

            target_live = round(
                prior_live + delta,
                2,
            )

            if target_live <= live_price + 0.01:
                canonical = "CALL"
                amount_bb = delta
                raise_to_bb = None
            else:
                canonical = "RAISE"
                amount_bb = None
                raise_to_bb = target_live
                live_price = target_live

        else:
            return PreservedActionReconciliation(
                False,
                [],
                f"unsupported qualified action {raw} for {seat}",
            )

        actions.append({
            "seat": seat,
            "action": canonical,
            "amount_bb": amount_bb,
            "raise_to_bb": raise_to_bb,
            "confidence": float(
                event.get("confidence") or 0.0
            ),
            "source": "deferred_inferred_action",
            "evidence": list(
                event.get("evidence") or []
            ),
            "ts": event.get("ts"),
        })

    return PreservedActionReconciliation(
        True,
        actions,
        "qualified preserved actions establish chronological preflop sequence",
    )
