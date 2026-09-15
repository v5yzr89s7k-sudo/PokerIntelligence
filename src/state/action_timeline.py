"""
Single-owner durable action timeline.

This module owns whether a physically observed poker action exists.

Other systems may enrich/refine an action, but failure of OCR, stack
settlement, API enrichment, snapshot work, or sizing work must never
erase an independently observed action.

An action may be rejected only through explicit contradictory evidence.
"""

from copy import deepcopy


ACTIVE_STATES = {
    "OBSERVED",
    "CONFIRMED",
    "REFINED",
}


def action_key(hand_token, street, seat):
    return (
        f"{str(hand_token or '')}:"
        f"{str(street or '').upper()}:"
        f"{str(seat or '')}"
    )


def _records(state):
    records = state.get("action_timeline")
    if not isinstance(records, list):
        records = []
        state["action_timeline"] = records
    return records


def find_action(
    state,
    *,
    hand_token,
    street,
    seat,
):
    key = action_key(
        hand_token,
        street,
        seat,
    )

    for item in _records(state):
        if (
            isinstance(item, dict)
            and item.get("key") == key
        ):
            return item

    return None


def observe_action(
    state,
    *,
    hand_token,
    street,
    seat,
    action,
    ts,
    source,
    confidence=None,
    evidence=None,
):
    """
    Create a durable action record once.

    Repeated physical evidence may strengthen the same record but
    never creates a competing owner for the same hand/street/seat.
    """
    hand_token = str(hand_token or "")
    street = str(street or "").upper()
    seat = str(seat or "")
    action = str(action or "").upper()

    if not hand_token or not street or not seat or not action:
        return state

    existing = find_action(
        state,
        hand_token=hand_token,
        street=street,
        seat=seat,
    )

    if existing is not None:
        existing.setdefault(
            "evidence",
            [],
        )

        for item in evidence or []:
            if item not in existing["evidence"]:
                existing["evidence"].append(item)

        if (
            confidence is not None
            and (
                existing.get("confidence") is None
                or confidence > existing["confidence"]
            )
        ):
            existing["confidence"] = confidence

        return state

    item = {
        "key": action_key(
            hand_token,
            street,
            seat,
        ),
        "hand_token": hand_token,
        "street": street,
        "seat": seat,
        "action": action,
        "status": "OBSERVED",
        "first_observed_ts": ts,
        "last_updated_ts": ts,
        "source": str(source or ""),
        "confidence": confidence,
        "evidence": list(evidence or []),
        "amount_bb": None,
        "raise_to_bb": None,
        "rejection_reason": None,
    }

    _records(state).append(item)

    return state


def refine_action(
    state,
    *,
    hand_token,
    street,
    seat,
    action=None,
    amount_bb=None,
    raise_to_bb=None,
    ts=None,
    source=None,
    confidence=None,
    evidence=None,
    confirmed=False,
):
    """
    Enrich the existing action in place.

    Refinement never creates a second semantic owner.
    """
    item = find_action(
        state,
        hand_token=hand_token,
        street=street,
        seat=seat,
    )

    if item is None:
        return state

    if item.get("status") == "REJECTED":
        return state

    if action:
        item["action"] = str(action).upper()

    if amount_bb is not None:
        item["amount_bb"] = amount_bb

    if raise_to_bb is not None:
        item["raise_to_bb"] = raise_to_bb

    if confidence is not None:
        item["confidence"] = confidence

    if source:
        item["source"] = str(source)

    if ts is not None:
        item["last_updated_ts"] = ts

    item["status"] = (
        "CONFIRMED"
        if confirmed
        else "REFINED"
    )

    item.setdefault(
        "evidence",
        [],
    )

    for value in evidence or []:
        if value not in item["evidence"]:
            item["evidence"].append(value)

    return state


def reject_action(
    state,
    *,
    hand_token,
    street,
    seat,
    reason,
    contradictory_evidence=False,
    ts=None,
):
    """
    Reject an observed action only when there is affirmative evidence
    contradicting the physical observation itself.

    Enrichment failure is never sufficient.
    """
    if not contradictory_evidence:
        return state

    item = find_action(
        state,
        hand_token=hand_token,
        street=street,
        seat=seat,
    )

    if item is None:
        return state

    item["status"] = "REJECTED"
    item["rejection_reason"] = str(reason or "")
    item["last_updated_ts"] = ts

    return state


def active_actions(state, hand_token=None):
    result = []

    for item in _records(state):
        if not isinstance(item, dict):
            continue

        if item.get("status") not in ACTIVE_STATES:
            continue

        if (
            hand_token is not None
            and str(item.get("hand_token") or "")
            != str(hand_token or "")
        ):
            continue

        result.append(deepcopy(item))

    return result


def project_action_to_canonical(
    state,
    *,
    hand,
    hand_token,
    street,
    seat,
):
    """
    Materialize one existing durable ActionTimeline owner into CanonicalHand.

    This function has no authority to infer whether an action happened.
    If ActionTimeline does not already own (hand, street, seat), nothing
    is written.

    Repeated projection is idempotent.
    """
    hand_token = str(hand_token or "")
    street = str(street or "").upper()
    seat = str(seat or "")

    item = find_action(
        state,
        hand_token=hand_token,
        street=street,
        seat=seat,
    )

    if (
        item is None
        or item.get("status")
        not in ACTIVE_STATES
    ):
        return None

    # A voluntary canonical action for this ownership key already
    # materialized. Never create a competing canonical record.
    for existing in hand.actions:
        if (
            str(
                getattr(existing, "street", "")
                or ""
            ).upper()
            == street
            and str(
                getattr(existing, "seat", "")
                or ""
            )
            == seat
            and str(
                getattr(existing, "action", "")
                or ""
            ).upper()
            not in {
                "POST_ANTE",
                "POST_SMALL_BLIND",
                "POST_BIG_BLIND",
            }
        ):
            return existing

    action = str(
        item.get("action") or ""
    ).upper()

    if not action:
        return None

    current_street = str(
        getattr(hand, "current_street", "")
        or ""
    ).upper()

    # v0.16 SINGLE CANONICAL PROJECTION GATEWAY
    #
    # Current-street actions use CanonicalHand's normal live-action
    # primitive because that primitive owns live commitment, betting
    # price, aggressor, fold state, and expected-pot consequences.
    #
    # Retrospective actions use the narrow boundary primitive so an
    # already-ended street can be reconstructed without mutating the
    # current live betting state.
    if street == current_street:
        return hand.add_action(
            seat=seat,
            action=action,
            amount_bb=item.get("amount_bb"),
            raise_to_bb=item.get("raise_to_bb"),
            confidence=item.get("confidence"),
            source=(
                item.get("source")
                or "action_timeline_projection"
            ),
            evidence=list(
                item.get("evidence")
                or []
            ),
            ts=item.get("first_observed_ts"),
        )

    return hand.add_boundary_action(
        street=street,
        seat=seat,
        action=action,
        amount_bb=item.get("amount_bb"),
        raise_to_bb=item.get("raise_to_bb"),
        confidence=item.get("confidence"),
        source=(
            item.get("source")
            or "action_timeline_projection"
        ),
        evidence=list(
            item.get("evidence")
            or []
        ),
        ts=item.get("first_observed_ts"),
    )


def presentation_overlay(state):
    """
    Project the durable timeline into the legacy presentation shape.

    This is intentionally a projection. The projection is disposable;
    the durable timeline is the owner.
    """
    hand_token = str(
        state.get("hand_token") or ""
    )

    result = {}

    for item in active_actions(
        state,
        hand_token=hand_token,
    ):
        key = (
            f"{item.get('street')}:"
            f"{item.get('seat')}"
        )

        result[key] = {
            "hand_token": item.get("hand_token"),
            "street": item.get("street"),
            "seat": item.get("seat"),
            "action": item.get("action"),
            "source": item.get("source"),
            "ts": item.get("first_observed_ts"),
            "confidence": item.get("confidence"),
            "amount_bb": item.get("amount_bb"),
            "raise_to_bb": item.get("raise_to_bb"),
        }

    return result


def compat_ingest_betting_action(
    tracker,
    inferred_action,
):
    """
    Legacy BettingRoundTracker.ingest() compatibility orchestrator.

    This function exists only for historical callers/tests.

    Action existence and canonical materialization remain outside
    BettingRoundTracker. Production does not use this compatibility path.
    """
    tracker._sync_street()

    item = tracker._action_dict(
        inferred_action
    )

    episode_id = int(
        item.get("episode_id") or 0
    )

    seat = item.get("seat") or "unknown"

    raw_action = str(
        item.get("action") or "UNKNOWN"
    ).upper()

    action_street = str(
        item.get("street")
        or tracker.hand.current_street
        or "unknown"
    ).upper()

    if episode_id <= 0:
        tracker._record_decision(
            episode_id,
            action_street,
            seat,
            raw_action,
            None,
            False,
            "missing or invalid episode id",
        )
        return None

    if (
        episode_id
        in tracker.processed_episode_ids
    ):
        return None

    tracker.processed_episode_ids.add(
        episode_id
    )

    resolution = (
        tracker.resolve_inferred_action(
            item
        )
    )

    if not resolution.get("resolved"):
        reason = str(
            resolution.get("reason")
            or "unresolved inferred action"
        )

        earlier_seats = list(
            resolution.get(
                "earlier_seats"
            )
            or []
        )

        if (
            reason
            == "earlier actors remain unresolved"
        ):
            tracker._record_decision(
                episode_id,
                action_street,
                seat,
                raw_action,
                None,
                False,
                (
                    "earlier actors remain unresolved; "
                    "quantitative action deferred without "
                    "queue mutation"
                ),
            )

            print(
                "[QUANTITATIVE_ACTION_DEFERRED]",
                f"street={action_street}",
                f"seat={seat}",
                f"earlier={earlier_seats}",
                f"raw_action={raw_action}",
                (
                    "canonical_candidate="
                    f"{resolution.get('action')}"
                ),
                flush=True,
            )

            tracker.processed_episode_ids.discard(
                episode_id
            )

            return None

        tracker._record_decision(
            episode_id,
            action_street,
            seat,
            raw_action,
            None,
            False,
            reason,
        )

        return None

    canonical_action = str(
        resolution.get("action") or ""
    ).upper()

    print(
        "[ACTION_ACCOUNTING] "
        f"seat={seat} "
        f"raw_action={raw_action} "
        f"canonical={canonical_action} "
        f"delta={resolution.get('delta_bb')} "
        f"prior_total={resolution.get('prior_committed_bb')} "
        f"ante={resolution.get('ante_committed_bb')} "
        f"prior_live={resolution.get('prior_live_commitment_bb')} "
        f"current_price={resolution.get('current_price_bb')} "
        f"target_live={resolution.get('target_commitment_bb')} "
        f"amount_bb={resolution.get('amount_bb')} "
        f"raise_to_bb={resolution.get('raise_to_bb')}",
        flush=True,
    )

    # Compatibility calls have no persistent state-machine ActionTimeline,
    # so create one ephemeral owner for this explicit legacy transaction.
    compatibility_state = {
        "action_timeline": [],
    }

    hand_token = str(
        tracker.hand.hand_id
        or "legacy-betting-ingest"
    )

    compatibility_state = observe_action(
        compatibility_state,
        hand_token=hand_token,
        street=action_street,
        seat=seat,
        action=canonical_action,
        ts=item.get("ts"),
        source="legacy_betting_ingest_compat",
        confidence=item.get("confidence"),
        evidence=list(
            item.get("evidence") or []
        ),
    )

    compatibility_state = refine_action(
        compatibility_state,
        hand_token=hand_token,
        street=action_street,
        seat=seat,
        action=canonical_action,
        amount_bb=resolution.get(
            "amount_bb"
        ),
        raise_to_bb=resolution.get(
            "raise_to_bb"
        ),
        ts=item.get("ts"),
        source="legacy_betting_ingest_compat",
        confidence=item.get("confidence"),
        evidence=list(
            item.get("evidence") or []
        ),
        confirmed=True,
    )

    canonical = project_action_to_canonical(
        compatibility_state,
        hand=tracker.hand,
        hand_token=hand_token,
        street=action_street,
        seat=seat,
    )

    if canonical is None:
        tracker.processed_episode_ids.discard(
            episode_id
        )

        tracker._record_decision(
            episode_id,
            action_street,
            seat,
            raw_action,
            None,
            False,
            "compatibility canonical projection failed",
        )

        return None

    return tracker.apply_resolved_action(
        inferred_action=item,
        resolution=resolution,
        canonical=canonical,
    )
