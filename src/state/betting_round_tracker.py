from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from src.observer.action_inference_engine import (
    UNKNOWN,
    BET_OR_RAISE,
    CALL_OR_RAISE,
    CALL,
    FOLD_OR_RESOLVED,
    TABLE_EVENT,
    POST_SMALL_BLIND,
    POST_BIG_BLIND,
)
from src.state.canonical_hand import CanonicalAction, CanonicalHand
from src.state.street_commitment_tracker import (
    StreetCommitmentTracker,
)


BET = "BET"
RAISE = "RAISE"

# Objective chip-commitment event used until sizing resolves the exact
# semantic action as CALL, BET, or RAISE.
VOLUNTARY_COMMIT = "VOLUNTARY_COMMIT"

# Forced posts are canonical poker events, not voluntary bets.
CANONICAL_POST_ANTE = "POST_ANTE"
CANONICAL_POST_SMALL_BLIND = "POST_SMALL_BLIND"
CANONICAL_POST_BIG_BLIND = "POST_BIG_BLIND"


@dataclass
class BettingRoundDecision:
    episode_id: int
    street: str
    seat: str
    inferred_action: str
    canonical_action: Optional[str]
    accepted: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class BettingRoundTracker:
    """
    Converts inferred perception actions into ordered CanonicalHand actions.

    This first phase:
    - distinguishes BET from RAISE
    - preserves CALL
    - preserves ambiguous evidence as UNKNOWN
    - rejects stale-street and table-level events
    - processes each episode only once
    """

    def __init__(
        self,
        hand: CanonicalHand,
        commitment_tracker=None,
    ):
        if not isinstance(hand, CanonicalHand):
            raise TypeError("hand must be a CanonicalHand")

        self.hand = hand
        self.commitment_tracker = (
            commitment_tracker
            or StreetCommitmentTracker()
        )
        self.street = hand.current_street
        self.has_open_bet = bool(
            hand.last_aggressor_seat
            or float(hand.current_bet_bb or 0.0) > 0.0
        )
        self.last_aggressor_seat = hand.last_aggressor_seat
        self.processed_episode_ids = set()
        self.decisions: List[BettingRoundDecision] = []

        self.commitment_tracker.initialize_street_order(
            self.street,
            self.hand.players_to_act,
        )
        self.commitment_tracker.sync_queue(
            self.street,
            self.hand.players_to_act,
        )

    @staticmethod
    def _action_dict(action: Any) -> Dict:
        if isinstance(action, dict):
            return action

        if hasattr(action, "to_dict"):
            return action.to_dict()

        raise TypeError(
            "inferred action must be an InferredAction or dictionary"
        )

    def _sync_street(self):
        current = self.hand.current_street

        if current == self.street:
            return

        self.street = current
        self.has_open_bet = False
        self.last_aggressor_seat = None

        self.hand.current_bet_bb = 0.0
        self.hand.last_aggressor_seat = None
        # CanonicalHand.set_board() has already initialized the new
        # street's action queue. Preserve it instead of clearing it here.
        self.commitment_tracker.reset_street(
            self.street
        )
        self.commitment_tracker.initialize_street_order(
            self.street,
            self.hand.players_to_act,
        )
        self.commitment_tracker.sync_queue(
            self.street,
            self.hand.players_to_act,
        )

    def _consume_action_queue(self, seat: str) -> List[str]:
        """
        Advance the canonical live-action queue through the acting seat.

        Seats preceding the observed actor are returned as skipped seats.
        This phase does not assign poker semantics to those skipped seats;
        passive fold inference is intentionally implemented separately.
        """
        queue = list(self.hand.players_to_act or [])

        if seat not in queue:
            return []

        actor_index = queue.index(seat)
        skipped = queue[:actor_index]

        self.hand.players_to_act = queue[actor_index + 1:]

        return skipped

    def advance_to_observed_actor(
        self,
        seat: str,
        *,
        ts=None,
        blocked_seats=None,
    ) -> List[CanonicalAction]:
        """
        Advance chronology to a newly observed actor without classifying
        that actor's quantitative action.

        Seats preceding the observed actor are passive only when no
        independent unresolved commitment evidence blocks the gap.
        """
        self._sync_street()

        queue = list(self.hand.players_to_act or [])

        if seat not in queue:
            return []

        actor_index = queue.index(seat)

        if actor_index <= 0:
            return []

        skipped_seats = queue[:actor_index]
        blocked = set(blocked_seats or [])

        unresolved = [
            skipped_seat
            for skipped_seat in skipped_seats
            if skipped_seat in blocked
        ]

        if unresolved:
            print(
                "[ACTION_CURSOR_BLOCKED]",
                f"street={self.hand.current_street}",
                f"actor={seat}",
                f"skipped={skipped_seats}",
                f"blocked={unresolved}",
                flush=True,
            )
            return []

        # Consume only the seats proven passive by the later actor.
        # Leave the observed actor at the head of the queue so the normal
        # inferred-action path still owns its semantic action and sizing.
        self.hand.players_to_act = queue[actor_index:]

        inferred = self._infer_skipped_actions(
            skipped_seats,
            ts=ts,
        )

        for skipped_seat in skipped_seats:
            self.commitment_tracker.consume_pending_action(
                self.hand.current_street,
                skipped_seat,
            )

            self.commitment_tracker.record_action(
                self.hand.current_street,
                skipped_seat,
                current_price=self.hand.current_bet_bb,
                last_aggressor=self.hand.last_aggressor_seat,
                betting_open=self.has_open_bet,
            )

        self.commitment_tracker.sync_queue(
            self.hand.current_street,
            self.hand.players_to_act,
        )

        print(
            "[ACTION_CURSOR_ADVANCE]",
            f"street={self.hand.current_street}",
            f"actor={seat}",
            f"resolved={skipped_seats}",
            f"remaining={self.hand.players_to_act}",
            flush=True,
        )

        return inferred

    def resolve_physically_completed_actor(
        self,
        seat: str,
        *,
        ts=None,
    ):
        """
        Resolve direct physical evidence for exactly the actor currently
        at the head of the canonical action queue.

        This method can never skip another unresolved player. The normal
        passive-action semantics remain authoritative:

        - preflop -> FOLD
        - postflop facing an open bet -> FOLD
        - postflop with no open bet -> CHECK

        Card disappearance is therefore chronology evidence, not an
        independent permission to inject an action out of order.
        """
        queue = list(
            self.hand.players_to_act
            or []
        )

        if not queue:
            return []

        if queue[0] != seat:
            print(
                "[PHYSICAL_ACTOR_DEFER] "
                f"street={self.hand.current_street} "
                f"seat={seat} "
                f"head={queue[0]}",
                flush=True,
            )
            return []

        inferred = self._infer_skipped_actions(
            [seat],
            ts=ts,
        )

        if not inferred:
            return []

        self.hand.players_to_act = queue[1:]

        self.commitment_tracker.consume_pending_action(
            self.hand.current_street,
            seat,
        )

        self.commitment_tracker.record_action(
            self.hand.current_street,
            seat,
            current_price=self.hand.current_bet_bb,
            last_aggressor=self.hand.last_aggressor_seat,
            betting_open=self.has_open_bet,
        )

        self.commitment_tracker.sync_queue(
            self.hand.current_street,
            self.hand.players_to_act,
        )

        print(
            "[PHYSICAL_ACTOR_RESOLVE] "
            f"street={self.hand.current_street} "
            f"seat={seat} "
            f"action={inferred[0].action} "
            f"remaining={self.hand.players_to_act}",
            flush=True,
        )

        return inferred


    def _infer_skipped_actions(
        self,
        skipped_seats: List[str],
        ts=None,
    ) -> List[CanonicalAction]:
        """
        Resolve seats skipped before an observed actor.

        Preflop skipped seats fold. Postflop skipped seats check when no
        voluntary bet is open, otherwise they fold.
        """
        if not skipped_seats:
            return []

        street = self.hand.current_street
        passive_action = (
            "CHECK"
            if street != "PREFLOP" and not self.has_open_bet
            else "FOLD"
        )

        inferred = []

        for skipped_seat in skipped_seats:
            player = self.hand.players.get(skipped_seat)

            if (
                player is None
                or player.folded
                or player.all_in
                or not player.active
            ):
                continue

            print(
                "[SKIPPED_ACTION]",
                f"street={street}",
                f"seat={skipped_seat}",
                f"inferred={passive_action}",
                f"open_bet={self.has_open_bet}",
                f"trigger=observed_actor_skip",
                flush=True,
            )

            inferred.append(
                self.hand.add_action(
                    seat=skipped_seat,
                    action=passive_action,
                    confidence=0.90,
                    source="action_order_inference",
                    evidence=[
                        "seat_skipped_before_observed_actor",
                        (
                            "no_open_postflop_bet"
                            if passive_action == "CHECK"
                            else "action_required_but_no_commitment_observed"
                        ),
                    ],
                    ts=ts,
                )
            )

            self.commitment_tracker.record_response(
                street,
                skipped_seat,
            )

        return inferred

    def _response_eligible_seats(self) -> List[str]:
        """
        Return players who can legally owe a response on the current street.
        """
        eligible = []

        for seat, player in self.hand.players.items():
            if (
                player.active
                and not player.folded
                and not player.all_in
            ):
                eligible.append(seat)

        return eligible

    def _record_decision(
        self,
        episode_id: int,
        street: str,
        seat: str,
        inferred_action: str,
        canonical_action: Optional[str],
        accepted: bool,
        reason: str,
    ):
        decision = BettingRoundDecision(
            episode_id=episode_id,
            street=street,
            seat=seat,
            inferred_action=inferred_action,
            canonical_action=canonical_action,
            accepted=accepted,
            reason=reason,
        )
        self.decisions.append(decision)
        return decision

    def _last_full_raise_increment_bb(
        self,
        street,
    ):
        """
        Reconstruct the most recent full betting increment from canonical
        same-street chronology.

        The big blind establishes the initial live price preflop.
        BET and RAISE actions subsequently advance the live price.
        """
        street = str(
            street or ""
        ).upper()

        live_price = 0.0
        last_increment = 0.0

        for existing in self.hand.actions:
            if str(
                getattr(existing, "street", "")
                or ""
            ).upper() != street:
                continue

            action_name = str(
                getattr(existing, "action", "")
                or ""
            ).upper()

            amount = getattr(
                existing,
                "amount_bb",
                None,
            )

            raise_to = getattr(
                existing,
                "raise_to_bb",
                None,
            )

            if (
                action_name == "POST_BIG_BLIND"
                and amount is not None
            ):
                new_price = float(amount)

                if new_price > live_price:
                    last_increment = (
                        new_price - live_price
                    )
                    live_price = new_price

                continue

            if (
                action_name == "BET"
                and amount is not None
            ):
                new_price = float(amount)

                if new_price > live_price:
                    last_increment = (
                        new_price - live_price
                    )
                    live_price = new_price

                continue

            if (
                action_name == "RAISE"
                and raise_to is not None
            ):
                new_price = float(raise_to)

                if new_price > live_price:
                    last_increment = (
                        new_price - live_price
                    )
                    live_price = new_price

        return round(
            max(0.0, last_increment),
            2,
        )


    def _classify_inferred_action(
        self,
        episode_id: int,
        action_street: str,
        seat: str,
        action: str,
    ):
        if action == POST_SMALL_BLIND:
            if action_street != "PREFLOP":
                self._record_decision(
                    episode_id,
                    action_street,
                    seat,
                    action,
                    None,
                    False,
                    "small blind post is only valid preflop",
                )
                return None

            canonical_action = CANONICAL_POST_SMALL_BLIND
            reason = "forced small blind preserved as canonical event"

        elif action == POST_BIG_BLIND:
            if action_street != "PREFLOP":
                self._record_decision(
                    episode_id,
                    action_street,
                    seat,
                    action,
                    None,
                    False,
                    "big blind post is only valid preflop",
                )
                return None

            canonical_action = CANONICAL_POST_BIG_BLIND
            reason = "forced big blind preserved as canonical event"

        elif action in {
            BET_OR_RAISE,
            CALL_OR_RAISE,
        }:
            # Preserve the richest honest semantic available instead of
            # collapsing both candidates into VOLUNTARY_COMMIT.
            canonical_action = action

            if action == CALL_OR_RAISE:
                reason = (
                    "call versus raise remains unresolved; "
                    "preserving inferred semantic"
                )
            else:
                reason = (
                    "bet versus raise remains unresolved; "
                    "preserving inferred semantic"
                )

        elif action == CALL:
            canonical_action = CALL
            reason = "call inference preserved"

        elif action == FOLD_OR_RESOLVED:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "fold versus visual resolution remains ambiguous",
            )
            return None

        elif action == TABLE_EVENT:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "table event is not a player action",
            )
            return None

        elif action == UNKNOWN:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "insufficient evidence; not added to canonical hand",
            )
            return None

        else:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                f"unsupported inferred action: {action}",
            )
            return None


        return canonical_action, reason

    def ingest(self, inferred_action: Any) -> Optional[CanonicalAction]:
        self._sync_street()
        item = self._action_dict(inferred_action)

        episode_id = int(item.get("episode_id") or 0)
        seat = item.get("seat") or "unknown"
        action = (item.get("action") or UNKNOWN).upper()
        action_street = (
            item.get("street")
            or self.hand.current_street
            or "unknown"
        ).upper()

        if episode_id <= 0:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "missing or invalid episode id",
            )
            return None

        if episode_id in self.processed_episode_ids:
            return None

        self.processed_episode_ids.add(episode_id)

        if action_street != self.hand.current_street:
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "action street does not match canonical hand street",
            )
            return None

        if seat in ("", "unknown", "table"):
            self._record_decision(
                episode_id,
                action_street,
                seat,
                action,
                None,
                False,
                "action has no attributable player seat",
            )
            return None

        classification = self._classify_inferred_action(
            episode_id=episode_id,
            action_street=action_street,
            seat=seat,
            action=action,
        )

        if classification is None:
            return None

        canonical_action, reason = classification

        measurements = item.get("measurements") or {}
        stack_change = measurements.get("stack_change") or {}

        delta_bb = stack_change.get("delta_bb")
        amount_bb = None
        raise_to_bb = None

        if delta_bb is not None:
            try:
                delta_bb = round(float(delta_bb), 2)
            except (TypeError, ValueError):
                delta_bb = None

        if delta_bb is not None and delta_bb > 0:
            player = self.hand.players.get(seat)
            prior_committed = 0.0

            if player is not None:
                prior_committed = float(
                    player.committed_by_street.get(
                        self.hand.current_street,
                        0.0,
                    )
                    or 0.0
                )

            ante_committed = self.hand.ante_committed_bb(
                seat,
                self.hand.current_street,
            )

            # Total canonical commitment contains ante dead money. Calls and
            # raises must instead be classified against the live commitment,
            # which excludes the ante.
            prior_live_committed = round(
                max(
                    0.0,
                    prior_committed - ante_committed,
                ),
                2,
            )

            current_price = round(
                float(self.hand.current_bet_bb or 0.0),
                2,
            )
            target_commitment = round(
                prior_live_committed + delta_bb,
                2,
            )
            tolerance = 0.05

            stack_confidence = float(
                stack_change.get(
                    "stack_read_confidence"
                )
                or 0.0
            )

            stack_mode = str(
                stack_change.get(
                    "stack_read_mode"
                )
                or ""
            ).lower()

            trusted_stack_sizing = bool(
                stack_confidence >= 0.95
                and stack_mode
                not in {
                    "",
                    "unknown",
                    "unresolved",
                    "empty",
                }
            )

            last_full_increment = (
                self._last_full_raise_increment_bb(
                    self.hand.current_street
                )
            )

            minimum_full_raise_to = (
                round(
                    current_price
                    + last_full_increment,
                    2,
                )
                if (
                    current_price > tolerance
                    and last_full_increment > tolerance
                )
                else None
            )

            if canonical_action in {
                BET_OR_RAISE,
                CALL_OR_RAISE,
            }:
                if current_price <= tolerance:
                    canonical_action = BET
                    amount_bb = delta_bb
                    reason = (
                        "chip commitment opened betting with no live "
                        "price; resolved as BET"
                    )

                elif target_commitment <= current_price + tolerance:
                    canonical_action = CALL
                    amount_bb = delta_bb
                    reason = (
                        "total street commitment matched the live "
                        "price; resolved as CALL"
                    )

                elif (
                    canonical_action == CALL_OR_RAISE
                    and trusted_stack_sizing
                    and minimum_full_raise_to is not None
                    and target_commitment
                    < minimum_full_raise_to - tolerance
                ):
                    canonical_action = CALL
                    amount_bb = delta_bb
                    reason = (
                        "trusted stack-derived commitment exceeded "
                        "the live price but did not reach the minimum "
                        "full raise-to amount; resolved as CALL"
                    )

                else:
                    canonical_action = RAISE
                    raise_to_bb = target_commitment
                    reason = (
                        "total street commitment established a "
                        "raise-sized live commitment; resolved as RAISE"
                    )

            elif canonical_action == RAISE:
                raise_to_bb = target_commitment

            elif canonical_action in {
                CALL,
                BET,
            }:
                amount_bb = delta_bb

        # Quantitative evidence for one actor does not independently prove
        # the actions of earlier seats in the canonical traversal queue.
        #
        # If this actor is not currently at the head of the live queue,
        # chronology is unresolved. Defer the episode without mutating the
        # queue, fabricating passive actions, or marking the episode processed.
        #
        # Explicit chronology evidence owns skipped-seat resolution.
        forced_actions = {
            CANONICAL_POST_ANTE,
            CANONICAL_POST_SMALL_BLIND,
            CANONICAL_POST_BIG_BLIND,
        }

        if canonical_action not in forced_actions:
            # StreetCommitmentTracker is the durable authority for outstanding
            # betting obligations. CanonicalHand.players_to_act is a
            # materialized traversal field and may temporarily lag after
            # boundary or historical reconciliation.
            #
            # Quantitative evidence may therefore be admitted only against the
            # durable obligation queue. It must never use a stale materialized
            # predecessor as evidence that the predecessor acted.
            authoritative_queue = list(
                self.commitment_tracker.players_owing_action(
                    action_street
                )
                or []
            )

            if seat in authoritative_queue:
                actor_index = authoritative_queue.index(seat)

                if actor_index > 0:
                    skipped_seats = authoritative_queue[:actor_index]

                    self._record_decision(
                        episode_id,
                        action_street,
                        seat,
                        action,
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
                        f"earlier={skipped_seats}",
                        f"raw_action={action}",
                        f"canonical_candidate={canonical_action}",
                        flush=True,
                    )

                    # Deferred is not processed. The state-machine replay
                    # path may retry this episode after chronology advances.
                    self.processed_episode_ids.discard(
                        episode_id
                    )

                    return None

            # Quantitative evidence owns only this actor. Remove exactly this
            # seat from the materialized canonical queue if it is still
            # present; never consume stale predecessors.
            self.hand.players_to_act = [
                pending_seat
                for pending_seat in (
                    self.hand.players_to_act
                    or []
                )
                if pending_seat != seat
            ]

        # Mandatory blinds are seeded during hand initialization.
        # Never duplicate them from later visual inference.
        if canonical_action in {
            CANONICAL_POST_ANTE,
            CANONICAL_POST_SMALL_BLIND,
            CANONICAL_POST_BIG_BLIND,
        }:
            already_recorded = any(
                existing.seat == seat
                and existing.street == "PREFLOP"
                and existing.action == canonical_action
                for existing in self.hand.actions
            )

            if already_recorded:
                self._record_decision(
                    episode_id,
                    action_street,
                    seat,
                    action,
                    None,
                    False,
                    "forced blind already present",
                )
                return None

        print(
            "[ACTION_ACCOUNTING] "
            f"seat={seat} "
            f"raw_action={action} "
            f"canonical={canonical_action} "
            f"delta={delta_bb} "
            f"prior_total={prior_committed if delta_bb is not None else None} "
            f"ante={ante_committed if delta_bb is not None else None} "
            f"prior_live={prior_live_committed if delta_bb is not None else None} "
            f"current_price={current_price if delta_bb is not None else None} "
            f"target_live={target_commitment if delta_bb is not None else None} "
            f"amount_bb={amount_bb} "
            f"raise_to_bb={raise_to_bb}",
            flush=True,
        )

        canonical = self.hand.add_action(
            seat=seat,
            action=canonical_action,
            amount_bb=amount_bb,
            raise_to_bb=raise_to_bb,
            confidence=item.get("confidence"),
            source="betting_round_tracker",
            evidence=list(item.get("evidence") or []),
            ts=item.get("ts"),
        )

        self.commitment_tracker.ingest(
            canonical
        )

        # Forced blinds and unresolved voluntary commitments are not
        # sufficient evidence of aggression. Only resolved BET or RAISE
        # events may establish the last aggressor.
        if canonical_action in (BET, RAISE):
            self.has_open_bet = True
            self.last_aggressor_seat = seat
            self.hand.last_aggressor_seat = seat

            self.commitment_tracker.open_response_queue(
                self.hand.current_street,
                seat,
                self._response_eligible_seats(),
            )

        elif canonical_action not in {
            CANONICAL_POST_ANTE,
            CANONICAL_POST_SMALL_BLIND,
            CANONICAL_POST_BIG_BLIND,
        }:
            self.commitment_tracker.record_response(
                self.hand.current_street,
                seat,
            )

        self.commitment_tracker.sync_queue(
            self.hand.current_street,
            self.hand.players_to_act,
        )

        self.commitment_tracker.record_action(
            self.hand.current_street,
            seat,
            current_price=self.hand.current_bet_bb,
            last_aggressor=self.hand.last_aggressor_seat,
            betting_open=self.has_open_bet,
        )

        self._record_decision(
            episode_id,
            action_street,
            seat,
            action,
            canonical_action,
            True,
            reason,
        )

        return canonical

    def has_prior_commitment(
        self,
        street=None,
        excluding_seat=None,
    ):
        return self.commitment_tracker.has_prior_commitment(
            street or self.hand.current_street,
            excluding_seat=excluding_seat,
        )

    def committed_players(self, street=None):
        return self.commitment_tracker.committed_players(
            street or self.hand.current_street
        )

    def ingest_many(self, inferred_actions: List[Any]) -> List[CanonicalAction]:
        added = []

        for inferred_action in inferred_actions:
            canonical = self.ingest(inferred_action)
            if canonical is not None:
                added.append(canonical)

        return added

    def to_dict(self) -> dict:
        return {
            "street": self.street,
            "has_open_bet": self.has_open_bet,
            "last_aggressor_seat": self.last_aggressor_seat,
            "processed_episode_count": len(self.processed_episode_ids),
            "decision_count": len(self.decisions),
            "decisions": [
                decision.to_dict()
                for decision in self.decisions
            ],
        }
