"""
Production-neutral frame-driven hand observer.

This module owns evolving v0.17 hand/perception state.

It deliberately does NOT own:
- frame acquisition
- replay paths
- fixture identities
- expected actions
- legacy semantic/state-machine infrastructure

Frame processing will be migrated into this object incrementally while
the July 22 replay remains the deterministic regression harness.
"""

from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
)

from src.events.detectors.card_presence import (
    count_board_cards,
    hero_cards_visible,
    opponent_cards_visible,
)
from src.events.detectors.action_buttons_detector import (
    action_buttons_visible,
)
from src.events.detectors.bet_region_detector import (
    bet_region_occupancy,
)
from src.events.detectors.bet_region_state_tracker import (
    BetRegionStateTracker,
)
from src.events.detectors.frame_baseline import (
    FrameBaseline,
)

from src.vision.stack_reader import (
    read_stack,
)

from src.v017.fast_stack_resolver import (
    resolve_fast_stack,
)
from src.v017.chronology_completion import (
    predecessors_before_actor,
)
from src.v017.commitment_normalizer import (
    normalize_commitment_delta,
)
from src.v017.hand_engine import (
    HandEngine,
)
from src.v017.current_hand_renderer import (
    render_current_hand,
)

from src.v017.stack_motion_gate import (
    measure_stack_motion,
)


def common_mode_stack_shift_seats(
    observations,
    *,
    minimum_seats=3,
    delta_tolerance_bb=0.02,
):
    """
    Identify correlated same-frame stack displacement.

    A real poker action is seat-local. When at least three seats
    independently report effectively the same positive stack decrease
    in one physical frame, that shared displacement is common-mode
    measurement evidence and must not receive quantitative authority.

    This function owns no poker semantics.
    """
    groups = []

    for observation in observations:
        prior = observation.get("prior")
        value = observation.get("resolved_value")

        if prior is None or value is None:
            continue

        delta = round(
            float(prior) - float(value),
            2,
        )

        if delta <= 0.02:
            continue

        matched = None

        for group in groups:
            if abs(
                delta - group["delta"]
            ) <= delta_tolerance_bb:
                matched = group
                break

        if matched is None:
            matched = {
                "delta": delta,
                "seats": set(),
            }
            groups.append(matched)

        matched["seats"].add(
            str(observation.get("seat"))
        )

    rejected = set()

    for group in groups:
        if len(group["seats"]) >= minimum_seats:
            rejected.update(group["seats"])

    return rejected


@dataclass(frozen=True)
class FrameObservationResult:
    """
    Result of processing one physical frame.

    `text` is populated only when the authoritative product changed.
    """

    frame_id: Any
    events: tuple
    changed: bool
    text: Optional[str]


class FrameHandObserver:
    """
    Single v0.17 owner of evolving frame-driven hand state.

    Bootstrap information is supplied by the caller. No table identity,
    player identity, frame source, or replay fixture is embedded here.
    """

    def __init__(
        self,
        *,
        players: Sequence[Dict[str, Any]],
        action_order: Sequence[str],
        small_blind_seat: str,
        big_blind_seat: str,
        geometry: Dict[str, Any],
        trusted_stacks: Optional[
            Dict[str, float]
        ] = None,
        opponent_seats: Optional[
            Iterable[str]
        ] = None,
        quantitative_seats: Optional[
            Iterable[str]
        ] = None,
        hero_seat: str = "hero",
        hand_id: Optional[str] = None,
        stack_reader=read_stack,
    ):
        self.geometry = geometry
        self.stack_reader = stack_reader
        self.hero_seat = hero_seat
        self.hand_id = hand_id

        self.hand = HandEngine(
            players=players,
            action_order=list(
                action_order
            ),
            small_blind_seat=(
                small_blind_seat
            ),
            big_blind_seat=(
                big_blind_seat
            ),
        )

        self.trusted_stacks = dict(
            trusted_stacks or {}
        )

        if opponent_seats is None:
            opponent_seats = [
                seat
                for seat in action_order
                if seat != hero_seat
            ]

        self.opponent_seats = tuple(
            opponent_seats
        )

        if quantitative_seats is None:
            quantitative_seats = (
                self.trusted_stacks.keys()
            )

        self.quantitative_seats = tuple(
            quantitative_seats
        )

        self.events: List[
            Dict[str, Any]
        ] = []

        self.publications: List[
            Dict[str, Any]
        ] = []

        self.previous_frame = None
        self.previous_visibility: Dict[
            str,
            bool,
        ] = {}

        self.previous_hero_cards_visible = (
            None
        )

        # Physical Hero-turn sensor baseline only.
        # This state has no poker-semantic authority.
        self.previous_action_buttons_visible = (
            None
        )

        # Native-resolution physical commitment sensor.
        #
        # This state has no poker-semantic authority. It only
        # exposes independently confirmed chip occupancy to the
        # settlement boundary.
        self.bet_region_baseline = FrameBaseline(
            pixel_threshold=18,
            blur_size=3,
        )
        self.bet_region_tracker = (
            BetRegionStateTracker()
        )
        self.bet_region_baseline_initialized = False
        self.confirmed_bet_regions = set()

        # Frame-driven quantitative retry ownership.
        #
        # A physical stack-motion wake may occur while ACR is
        # animating/moving chips and the stack text is temporarily
        # unreadable. The wake must not be consumed by that one
        # unresolved OCR attempt.
        #
        # Retry ownership is narrow:
        #   - only the seat that physically woke;
        #   - only while same-seat commitment remains confirmed;
        #   - one retry per subsequent physical frame;
        #   - bounded attempts;
        #   - cleared immediately after quantitative resolution.
        self.quantitative_retry_pending = {}
        self.quantitative_retry_max_attempts = 8

        # Independent settlement-confirmation ownership.
        #
        # A resolved changed value is only the first observation
        # required by StackSettlementGate. Once motion/retry has
        # produced that value, keep the same seat scheduled for one
        # later physical frame so the gate can receive independent
        # temporal confirmation without requiring another motion
        # edge.
        self.quantitative_confirmation_pending = {}
        self.quantitative_confirmation_max_attempts = 3

        # Resolved physical stack evidence that is valid but cannot
        # yet cross the authoritative chronology frontier.
        #
        # Retention does NOT mutate HandEngine or trusted_stacks.
        # Evidence remains physical until normal quantitative
        # admission succeeds later.
        self.pending_quantitative_evidence = []

        # Objective card-disappearance evidence that belongs to a
        # later actor than the current authoritative chronology
        # frontier. Retention itself has no semantic authority.
        self.pending_card_disappearances = []

        # Objective next-street boundaries that arrived while prior
        # semantic chronology was still unresolved.
        #
        # Each retained item preserves the complete caller contract
        # needed for later admission. Retention itself has no
        # HandEngine authority.
        self.pending_street_boundaries = []

        # Physical perception baseline only.
        # This is not authoritative poker street state.
        self.previous_board_count: Optional[int] = (
            None
        )

        self.previous_text: Optional[str] = (
            None
        )

        # Semantic catch-up may consume multiple already-known
        # physical observations after one chronology release.
        # Suppress intermediate product projections and publish
        # only the final authoritative state.
        self._publication_defer_depth = 0
        self._publication_deferred_frame = None

    def _publish_if_changed(
        self,
        frame_id,
    ):
        """
        Publish a read-only projection of authoritative HandEngine state.

        This method has no semantic authority. It runs only after a
        successful admission has already mutated HandEngine.
        """

        if self._publication_defer_depth > 0:
            self._publication_deferred_frame = frame_id
            return None

        text = render_current_hand(
            self.hand,
            hand_id=self.hand_id,
        )

        if text == self.previous_text:
            return None

        publication = {
            "frame": frame_id,
            "action_count":
                len(self.hand.actions),
            "next_actor":
                self.hand.next_actor,
            "street":
                self.hand.street,
            "text": text,
        }

        self.publications.append(
            publication
        )
        self.previous_text = text

        return publication

    def _begin_publication_transaction(
        self,
    ):
        self._publication_defer_depth += 1


    def _end_publication_transaction(
        self,
        frame_id=None,
    ):
        if self._publication_defer_depth <= 0:
            raise AssertionError(
                "publication transaction underflow"
            )

        self._publication_defer_depth -= 1

        if self._publication_defer_depth > 0:
            return None

        deferred_frame = (
            frame_id
            if frame_id is not None
            else self._publication_deferred_frame
        )

        self._publication_deferred_frame = None

        if deferred_frame is None:
            return None

        return self._publish_if_changed(
            deferred_frame
        )


    def _stack_crop(
        self,
        frame,
        seat: str,
    ):
        rect = (
            self.geometry[
                "stack_regions"
            ][seat]
        )

        x = int(rect["x"])
        y = int(rect["y"])
        w = int(rect["width"])
        h = int(rect["height"])

        return frame[
            y:y + h,
            x:x + w,
        ]

    @property
    def next_actor(self):
        return self.hand.next_actor

    @property
    def street(self):
        return self.hand.street

    def _retain_pending_card_disappearance(
        self,
        seat: str,
        *,
        frame_id=None,
        physical_type=(
            "OPPONENT_CARDS_DISAPPEARED"
        ),
    ):
        """
        Preserve objective disappearance evidence that cannot yet
        cross the authoritative actor frontier.

        Identity is seat + physical frame. No HandEngine mutation
        occurs here.
        """

        retained = {
            "seat": seat,
            "frame_id": frame_id,
            "physical_type": physical_type,
        }

        for existing in self.pending_card_disappearances:
            if (
                existing.get("seat") == seat
                and existing.get("frame_id") == frame_id
            ):
                return

        self.pending_card_disappearances.append(
            retained
        )

        self.pending_card_disappearances.sort(
            key=lambda row: (
                int(
                    row.get("frame_id")
                    if row.get("frame_id") is not None
                    else -1
                ),
                str(row.get("seat", "")),
            )
        )

        print(
            "[CARD_DISAPPEARANCE_RETAINED]",
            f"frame={frame_id}",
            f"seat={seat}",
            f"next_actor={self.hand.next_actor}",
            flush=True,
        )


    def _admit_authoritative_card_disappearance(
        self,
        seat: str,
        *,
        frame_id=None,
        physical_type=(
            "OPPONENT_CARDS_DISAPPEARED"
        ),
    ):
        """
        Admit one disappearance whose seat is already authoritative.

        This is the semantic primitive used by both direct admission
        and backlog reconciliation. It deliberately does not open or
        close publication transactions and does not recursively drain
        other evidence classes.
        """

        if seat != self.hand.next_actor:
            return None

        before_actions = len(
            self.hand.actions
        )

        action = (
            self.hand
            .observe_cards_disappeared(
                seat
            )
        )

        if (
            len(self.hand.actions)
            != before_actions + 1
        ):
            raise AssertionError(
                "card disappearance admission "
                "did not append exactly one action"
            )

        event = {
            "frame": frame_id,
            "type":
                "CARD_DISAPPEARANCE_ADMITTED",
            "physical_type":
                physical_type,
            "seat": seat,
            "semantic_action":
                action,
        }

        self.events.append(event)

        return action


    def reconcile_pending_card_disappearances(
        self,
    ):
        """
        Consume retained disappearances only when their seat reaches
        the authoritative actor frontier.

        Continue until no retained card evidence can make further
        chronological progress. Every physical observation is
        consumed at most once.
        """

        admitted_events = []

        while self.pending_card_disappearances:
            next_actor = self.hand.next_actor

            if next_actor is None:
                break

            match_index = None

            for index, retained in enumerate(
                self.pending_card_disappearances
            ):
                if (
                    retained.get("seat")
                    == next_actor
                ):
                    match_index = index
                    break

            if match_index is None:
                break

            retained = (
                self.pending_card_disappearances
                .pop(match_index)
            )

            action = (
                self._admit_authoritative_card_disappearance(
                    retained["seat"],
                    frame_id=retained.get(
                        "frame_id"
                    ),
                    physical_type=retained.get(
                        "physical_type",
                        "OPPONENT_CARDS_DISAPPEARED",
                    ),
                )
            )

            if action is None:
                # Defensive: authority changed unexpectedly. Restore
                # ownership rather than discard physical evidence.
                self.pending_card_disappearances.insert(
                    match_index,
                    retained,
                )
                break

            event = self.events[-1]
            admitted_events.append(event)

            print(
                "[CARD_DISAPPEARANCE_RECONCILED]",
                f"frame={retained.get('frame_id')}",
                f"seat={retained.get('seat')}",
                f"action={action}",
                flush=True,
            )

        return tuple(admitted_events)


    def admit_card_disappearance(
        self,
        seat: str,
        *,
        frame_id=None,
        physical_type=(
            "OPPONENT_CARDS_DISAPPEARED"
        ),
    ):
        """
        Admit objective card-disappearance evidence into HandEngine.

        Physical disappearance is not semantic authority by itself.
        Out-of-order evidence is retained until its seat reaches the
        authoritative actor frontier.
        """

        if seat != self.hand.next_actor:
            self._retain_pending_card_disappearance(
                seat,
                frame_id=frame_id,
                physical_type=physical_type,
            )
            return None

        self._begin_publication_transaction()

        try:
            action = (
                self._admit_authoritative_card_disappearance(
                    seat,
                    frame_id=frame_id,
                    physical_type=physical_type,
                )
            )

            # First consume quantitative evidence because it may
            # advance the actor frontier through commitments.
            self.reconcile_pending_evidence()

            # Then consume objective folds that have become
            # authoritative.
            self.reconcile_pending_card_disappearances()

            # Card catch-up may itself expose another retained
            # quantitative observation.
            self.reconcile_pending_evidence()

            # Only after action evidence is exhausted may a retained
            # physical street boundary cross.
            self.reconcile_pending_street_boundaries()

            self._publication_deferred_frame = (
                frame_id
            )

        finally:
            self._end_publication_transaction(
                frame_id
            )

        return action


    def _retain_blocked_quantitative_evidence(
        self,
        observation: Dict[str, Any],
    ):
        """
        Preserve valid physical evidence that is temporarily blocked
        by an unresolved semantic predecessor.

        Identity is the original physical seat/frame pair. Retention
        never advances trusted quantitative or HandEngine state.
        """

        retained = dict(observation)

        seat = str(
            retained.get("seat")
        )
        frame = retained.get("frame")

        for existing in self.pending_quantitative_evidence:
            if (
                existing.get("seat") == seat
                and existing.get("frame") == frame
            ):
                return

        self.pending_quantitative_evidence.append(
            retained
        )

        self.pending_quantitative_evidence.sort(
            key=lambda row: (
                int(
                    row.get("frame")
                    if row.get("frame") is not None
                    else -1
                ),
                str(row.get("seat", "")),
            )
        )

        print(
            "[QUANTITATIVE_RETAINED]",
            f"frame={frame}",
            f"seat={seat}",
            f"value={retained.get('resolved_value')}",
            flush=True,
        )


    def reconcile_pending_evidence(
        self,
    ):
        """
        Retry retained physical evidence against current authoritative
        chronology in original frame order.

        Still-blocked evidence remains retained. Successful evidence
        is consumed exactly once by normal admission.
        """

        if not self.pending_quantitative_evidence:
            return ()

        pending = list(
            self.pending_quantitative_evidence
        )

        self.pending_quantitative_evidence = []

        emitted = []

        for observation in pending:
            seat = str(
                observation.get("seat")
            )

            before_stack = (
                self.trusted_stacks.get(seat)
            )
            before_actions = len(
                self.hand.actions
            )

            admitted = (
                self.admit_quantitative_observation(
                    observation
                )
            )

            after_stack = (
                self.trusted_stacks.get(seat)
            )
            after_actions = len(
                self.hand.actions
            )

            if admitted:
                emitted.extend(admitted)

                print(
                    "[QUANTITATIVE_RECONCILED]",
                    f"frame={observation.get('frame')}",
                    f"seat={seat}",
                    f"value={observation.get('resolved_value')}",
                    flush=True,
                )

                continue

            consumed = bool(
                after_stack != before_stack
                or after_actions != before_actions
            )

            if consumed:
                continue

            # If normal admission hit blocked_predecessors again,
            # it has already re-retained the observation. If some
            # other non-consuming rejection occurred, do not invent
            # authority by forcing it back into the backlog.

        return tuple(emitted)


    def clear_quantitative_ownership(
        self,
        seat: str,
    ):
        """
        Clear observer-owned work for one quantitatively consumed action.

        This does not disable future perception for the seat. A later
        physical stack transition, including on a later street, may
        acquire fresh retry/confirmation ownership normally.
        """

        seat = str(seat)

        retry = self.quantitative_retry_pending.pop(
            seat,
            None,
        )

        confirmation = (
            self.quantitative_confirmation_pending.pop(
                seat,
                None,
            )
        )

        if (
            retry is not None
            or confirmation is not None
        ):
            print(
                "[QUANTITATIVE_OWNERSHIP_CLEARED]",
                f"seat={seat}",
                f"retry={retry is not None}",
                f"confirmation="
                f"{confirmation is not None}",
                flush=True,
            )

    def _quantitative_commitment_preflight(
        self,
        *,
        seat,
        normalized_delta_bb,
        all_in_confirmed=False,
    ):
        """
        Validate a settled physical commitment against the current
        authoritative betting state before it may reach HandEngine.

        Temporal settlement establishes measurement credibility only.
        It does not establish that the measurement represents a legal
        poker commitment.

        HandEngine remains the strict semantic authority.
        """

        player = self.hand.players[seat]

        prior_commitment = float(
            player.street_commitment_bb
        )

        delta = float(
            normalized_delta_bb
        )

        price = float(
            self.hand.current_price_bb
        )

        target = (
            prior_commitment
            + delta
        )

        if (
            target + 0.02 < price
            and not all_in_confirmed
        ):
            return {
                "allowed": False,
                "reason": "below_current_price",
                "prior_commitment_bb":
                    prior_commitment,
                "normalized_delta_bb":
                    delta,
                "target_commitment_bb":
                    target,
                "current_price_bb":
                    price,
                "all_in_confirmed":
                    bool(all_in_confirmed),
            }

        return {
            "allowed": True,
            "reason": None,
            "prior_commitment_bb":
                prior_commitment,
            "normalized_delta_bb":
                delta,
            "target_commitment_bb":
                target,
            "current_price_bb":
                price,
            "all_in_confirmed":
                bool(all_in_confirmed),
        }

    def admit_terminal_stack_return(
        self,
        observation: Dict[str, Any],
    ):
        """
        Admit a physically observed post-terminal uncalled return.

        This lane is intentionally separate from quantitative commitment
        admission. Stack increases can never represent wagers.

        Authority is narrow:
          - HandEngine already owns UNCONTESTED completion;
          - seat is the sole authoritative winner;
          - HandEngine exposes a positive unmatched commitment;
          - one raw OCR candidate exactly equals trusted stack plus that
            authoritative unmatched amount.

        The OCR observation confirms a predetermined accounting value.
        It does not infer the return amount.
        """
        if (
            observation.get("type")
            != "STACK_QUANTITATIVE_OBSERVATION"
        ):
            return ()

        if not self.hand.hand_complete:
            return ()

        if (
            self.hand.completion_reason
            != "UNCONTESTED"
        ):
            return ()

        winners = list(
            self.hand.winner_seats
        )

        if len(winners) != 1:
            return ()

        seat = str(
            observation.get("seat")
        )

        if seat != winners[0]:
            return ()

        if seat not in self.trusted_stacks:
            return ()

        expected_return = (
            self.hand
            .unmatched_commitment_bb(
                seat
            )
        )

        if expected_return <= 0.02:
            return ()

        prior = round(
            float(
                self.trusted_stacks[seat]
            ),
            2,
        )

        expected_value = round(
            prior + expected_return,
            2,
        )

        candidates = []

        for row in (
            observation.get("raw")
            or []
        ):
            value = row.get(
                "stack_bb"
            )

            if value is None:
                continue

            candidates.append(
                round(
                    float(value),
                    2,
                )
            )

        # Preserve the normal reader's top-level value too when present.
        reader_value = observation.get(
            "reader_value"
        )

        if reader_value is not None:
            candidates.append(
                round(
                    float(reader_value),
                    2,
                )
            )

        observed_value = next(
            (
                value
                for value in candidates
                if abs(
                    value
                    - expected_value
                ) <= 0.02
            ),
            None,
        )

        if observed_value is None:
            return ()

        amount = (
            self.hand
            .observe_uncalled_return(
                seat,
                expected_return,
            )
        )

        self.trusted_stacks[seat] = (
            observed_value
        )

        event = {
            "frame":
                observation.get("frame"),
            "type":
                "UNCALLED_RETURN_ADMITTED",
            "seat": seat,
            "prior": prior,
            "resolved_value":
                observed_value,
            "amount_bb": amount,
            "expected_value":
                expected_value,
        }

        self.events.append(event)

        self._publish_if_changed(
            observation.get("frame")
        )

        print(
            "[UNCALLED_RETURN_ADMITTED]",
            f"frame={observation.get('frame')}",
            f"seat={seat}",
            f"prior={prior}",
            f"value={observed_value}",
            f"amount={amount}",
            flush=True,
        )

        return (event,)

    def admit_quantitative_observation(
        self,
        observation: Dict[str, Any],
        *,
        all_in_confirmed=False,
    ):
        """
        Admit one resolved physical stack observation.

        The physical lane may wake repeatedly. Semantic mutation occurs
        here only for a new positive delta belonging to a seat that is
        still present in authoritative pending chronology.
        """

        if (
            observation.get("type")
            != "STACK_QUANTITATIVE_OBSERVATION"
        ):
            raise ValueError(
                "not a quantitative stack observation"
            )

        seat = observation["seat"]

        if seat not in self.trusted_stacks:
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=seat_not_trusted",
                f"trusted={sorted(self.trusted_stacks.keys())}",
                flush=True,
            )
            return ()

        if not observation.get("resolved"):
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=unresolved",
                flush=True,
            )
            return ()

        value = observation.get(
            "resolved_value"
        )

        if value is None:
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=value_none",
                flush=True,
            )
            return ()

        # Recompute against authoritative state. The physical event's
        # prior may have been stale when perception produced it.
        prior = float(
            self.trusted_stacks[seat]
        )
        value = float(value)

        physical_delta = round(
            prior - value,
            2,
        )

        # Unchanged values / false wakes have no semantic authority.
        if physical_delta <= 0.02:
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=no_positive_delta",
                f"prior={prior}",
                f"value={value}",
                f"delta={physical_delta}",
                flush=True,
            )
            return ()

        # Old observations cannot replay an already-consumed actor.
        if seat not in self.hand.pending_to_act:
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=seat_not_pending",
                f"next_actor={self.hand.next_actor}",
                f"pending={list(self.hand.pending_to_act)}",
                flush=True,
            )
            return ()

        emitted = []

        # A later actor's positive commitment objectively proves that
        # pending predecessors completed before that actor.
        if (
            self.hand.next_actor is not None
            and seat != self.hand.next_actor
        ):
            predecessors = (
                predecessors_before_actor(
                    self.hand.pending_to_act,
                    seat,
                )
            )

            # Preflight the complete predecessor chain before
            # mutating HandEngine. Later quantitative evidence proves
            # chronology ordering, but cannot identify an earlier
            # actor's action while that actor is still facing a price.
            blocked_predecessors = []

            for predecessor in predecessors:
                player = self.hand.players[
                    predecessor
                ]

                if (
                    player.street_commitment_bb
                    + 0.02
                    < self.hand.current_price_bb
                ):
                    blocked_predecessors.append(
                        predecessor
                    )

            if blocked_predecessors:
                print(
                    "[QUANTITATIVE_REJECT]",
                    f"frame={observation.get('frame')}",
                    f"seat={seat}",
                    "reason=blocked_predecessors",
                    f"next_actor={self.hand.next_actor}",
                    f"pending={list(self.hand.pending_to_act)}",
                    f"blocked={blocked_predecessors}",
                    f"price={self.hand.current_price_bb}",
                    flush=True,
                )

                self._retain_blocked_quantitative_evidence(
                    observation
                )

                return ()

            for predecessor in predecessors:
                action = (
                    self.hand
                    .observe_no_commitment(
                        predecessor
                    )
                )

                event = {
                    "frame":
                        observation.get(
                            "frame"
                        ),
                    "type":
                        "CHRONOLOGY_COMPLETION",
                    "seat": predecessor,
                    "proved_by": seat,
                    "semantic_action":
                        action,
                }

                self.events.append(event)
                emitted.append(event)

        if self.hand.next_actor != seat:
            raise ValueError(
                "quantitative actor did not become "
                "authoritative: "
                f"seat={seat} "
                f"next_actor={self.hand.next_actor}"
            )

        player = self.hand.players[seat]

        measurement = (
            normalize_commitment_delta(
                observed_delta_bb=
                    physical_delta,
                prior_street_commitment_bb=(
                    player.street_commitment_bb
                ),
                current_price_bb=(
                    self.hand.current_price_bb
                ),
            )
        )

        preflight = (
            self._quantitative_commitment_preflight(
                seat=seat,
                normalized_delta_bb=(
                    measurement.normalized_delta_bb
                ),
                all_in_confirmed=all_in_confirmed,
            )
        )

        if not preflight["allowed"]:
            print(
                "[QUANTITATIVE_REJECT]",
                f"frame={observation.get('frame')}",
                f"seat={seat}",
                "reason=below_current_price",
                (
                    "prior_commitment="
                    f"{preflight['prior_commitment_bb']}"
                ),
                (
                    "delta="
                    f"{preflight['normalized_delta_bb']}"
                ),
                (
                    "target="
                    f"{preflight['target_commitment_bb']}"
                ),
                (
                    "price="
                    f"{preflight['current_price_bb']}"
                ),
                (
                    "all_in_confirmed="
                    f"{bool(all_in_confirmed)}"
                ),
                flush=True,
            )

            return tuple(emitted)

        action = (
            self.hand
            .observe_stack_commitment(
                seat,
                measurement.normalized_delta_bb,
                all_in_confirmed=all_in_confirmed,
            )
        )

        # Advance trusted quantitative state only after successful
        # semantic admission.
        self.trusted_stacks[seat] = value

        event = {
            "frame":
                observation.get("frame"),
            "type":
                "QUANTITATIVE_ADMITTED",
            "seat": seat,
            "prior": prior,
            "resolved_value": value,
            "physical_delta_bb":
                physical_delta,
            "normalized_delta_bb":
                measurement.normalized_delta_bb,
            "snapped_to_call_price":
                measurement.snapped_to_call_price,
            "semantic_action": action,
        }

        self.events.append(event)
        emitted.append(event)

        # A successful quantitative admission may advance the
        # authoritative actor frontier onto physical evidence that
        # arrived earlier in this frame or in a prior frame.
        #
        # Catch that evidence up atomically. In particular:
        #
        #   later-actor card disappearance arrives
        #       -> retained
        #   predecessor quantitative action settles
        #       -> frontier advances
        #   retained disappearance
        #       -> must become authoritative immediately
        #
        # Do not call reconcile_pending_evidence() here before the
        # direct quantitative admission returns: that reconciler itself
        # enters admit_quantitative_observation(). Instead drain the
        # other evidence classes first, then allow retained quantitative
        # work exposed by those folds to run, then drain folds once more.
        self._begin_publication_transaction()

        try:
            self.reconcile_pending_card_disappearances()

            reconciled_quantitative = (
                self.reconcile_pending_evidence()
            )
            if reconciled_quantitative:
                emitted.extend(
                    reconciled_quantitative
                )

            self.reconcile_pending_card_disappearances()

            self.reconcile_pending_street_boundaries()

            self._publication_deferred_frame = (
                observation.get("frame")
            )

        finally:
            self._end_publication_transaction(
                observation.get("frame")
            )

        return tuple(emitted)

    def _retain_pending_street_boundary(
        self,
        observation: Dict[str, Any],
        *,
        action_order: Sequence[str],
        board: Sequence[str],
        complete_pending: bool,
    ):
        """
        Preserve an objective expected-next-street boundary whose
        prior semantic street cannot yet close.

        Identity is physical boundary type + frame. This method never
        mutates HandEngine.
        """

        retained = {
            "observation": dict(observation),
            "action_order": list(action_order),
            "board": list(board),
            "complete_pending": bool(
                complete_pending
            ),
        }

        frame = observation.get("frame")
        typ = observation.get("type")

        for existing in self.pending_street_boundaries:
            existing_observation = (
                existing.get("observation")
                or {}
            )

            if (
                existing_observation.get("frame")
                == frame
                and existing_observation.get("type")
                == typ
            ):
                return

        self.pending_street_boundaries.append(
            retained
        )

        self.pending_street_boundaries.sort(
            key=lambda row: (
                int(
                    (
                        row.get("observation")
                        or {}
                    ).get("frame")
                    if (
                        row.get("observation")
                        or {}
                    ).get("frame") is not None
                    else -1
                ),
                str(
                    (
                        row.get("observation")
                        or {}
                    ).get("type", "")
                ),
            )
        )

        print(
            "[STREET_BOUNDARY_RETAINED]",
            f"frame={frame}",
            f"type={typ}",
            f"street={self.hand.street}",
            f"next_actor={self.hand.next_actor}",
            flush=True,
        )


    def reconcile_pending_street_boundaries(
        self,
    ):
        """
        Re-attempt retained physical street boundaries in original
        frame order.

        A boundary remains pending only while it is still the expected
        next street and semantic chronology continues to block it.
        Successful boundaries are consumed exactly once.
        """

        if not self.pending_street_boundaries:
            return ()

        pending = list(
            self.pending_street_boundaries
        )

        self.pending_street_boundaries = []

        emitted = []

        for retained in pending:
            observation = dict(
                retained["observation"]
            )

            before_street = self.hand.street

            # The caller owns postflop ordering, but eligibility is
            # authoritative HandEngine state at admission time.
            #
            # A retained boundary may wait while earlier physical
            # evidence resolves folds. Preserve caller ordering while
            # removing seats that are now authoritatively ineligible.
            retained_order = list(
                retained["action_order"]
            )

            reconciled_order = [
                seat
                for seat in retained_order
                if (
                    seat in self.hand.players
                    and self.hand.players[seat].dealt_in
                    and not self.hand.players[seat].folded
                )
            ]

            if reconciled_order != retained_order:
                print(
                    "[STREET_ORDER_REVALIDATED]",
                    f"frame={observation.get('frame')}",
                    f"original={retained_order}",
                    f"current={reconciled_order}",
                    flush=True,
                )

            result = self.admit_street_boundary(
                observation,
                action_order=reconciled_order,
                board=list(
                    retained["board"]
                ),
                complete_pending=bool(
                    retained["complete_pending"]
                ),
            )

            if result:
                emitted.extend(result)

                print(
                    "[STREET_BOUNDARY_RECONCILED]",
                    f"frame={observation.get('frame')}",
                    f"type={observation.get('type')}",
                    f"from={before_street}",
                    f"to={self.hand.street}",
                    flush=True,
                )

        return tuple(emitted)


    def admit_street_boundary(
        self,
        observation: Dict[str, Any],
        *,
        action_order: Sequence[str],
        board: Sequence[str],
        complete_pending: bool = False,
    ):
        """
        Admit one objective physical street boundary.

        Admission requires the prior betting street to already be
        semantically closed. Physical boundary evidence does not invent
        unresolved player actions.

        Board identity and next-street action order are caller supplied.
        """
        boundary_type = observation.get(
            "type"
        )

        boundary_contract = {
            "FLOP_BOUNDARY_PHYSICAL":
                ("FLOP", 3),
            "TURN_BOUNDARY_PHYSICAL":
                ("TURN", 4),
            "RIVER_BOUNDARY_PHYSICAL":
                ("RIVER", 5),
        }

        if boundary_type not in boundary_contract:
            raise ValueError(
                "not a physical street boundary: "
                f"{boundary_type}"
            )

        street, expected_count = (
            boundary_contract[
                boundary_type
            ]
        )

        try:
            board_count = int(
                observation.get(
                    "board_count"
                )
            )
        except (TypeError, ValueError):
            raise ValueError(
                "street boundary missing valid "
                "board_count"
            )

        if board_count != expected_count:
            raise ValueError(
                "physical boundary board count "
                "does not match street: "
                f"street={street} "
                f"board_count={board_count} "
                f"expected={expected_count}"
            )

        progression = {
            "PREFLOP": "FLOP",
            "FLOP": "TURN",
            "TURN": "RIVER",
        }

        expected_street = progression.get(
            self.hand.street
        )

        # Stale, duplicate, skipped, and backward physical evidence
        # has no semantic authority.
        observed_board = list(board)

        if len(observed_board) != expected_count:
            raise ValueError(
                "board identity length does not "
                "match physical boundary: "
                f"street={street} "
                f"cards={len(observed_board)} "
                f"expected={expected_count}"
            )


        if street != expected_street:
            street_rank = {
                "PREFLOP": 0,
                "FLOP": 1,
                "TURN": 2,
                "RIVER": 3,
            }

            current_rank = street_rank[
                self.hand.street
            ]
            observed_rank = street_rank[
                street
            ]

            if observed_rank > current_rank:
                # Physical board progression can outrun semantic
                # chronology by more than one street. Preserve future
                # objective evidence without granting it authority
                # before each predecessor street is admitted.
                self._retain_pending_street_boundary(
                    observation,
                    action_order=action_order,
                    board=observed_board,
                    complete_pending=complete_pending,
                )

                print(
                    "[FUTURE_STREET_BOUNDARY_RETAINED]",
                    f"frame={observation.get('frame')}",
                    f"type={boundary_type}",
                    f"semantic_street={self.hand.street}",
                    f"observed_street={street}",
                    flush=True,
                )

            # Stale/backward/duplicate boundaries remain non-authoritative.
            return ()

        # Normal admission requires prior semantic closure.
        #
        # When explicitly authorized, the physical appearance of
        # the next board street is objective chronology proof that
        # every still-pending prior-street actor completed before
        # this boundary. HandEngine remains the sole authority for
        # the zero-commitment semantic action.
        emitted = []

        if self.hand.next_actor is not None:
            if not complete_pending:
                self._retain_pending_street_boundary(
                    observation,
                    action_order=action_order,
                    board=observed_board,
                    complete_pending=complete_pending,
                )
                return ()

            pending = list(
                self.hand.pending_to_act
            )

            # Preflight the complete pending chain before
            # mutating HandEngine. A physical next-street boundary
            # proves that these actors completed action, but it cannot
            # identify a non-zero-price action.
            blocked_pending = []

            for pending_seat in pending:
                player = self.hand.players[
                    pending_seat
                ]

                if (
                    player.street_commitment_bb
                    + 0.02
                    < self.hand.current_price_bb
                ):
                    blocked_pending.append(
                        pending_seat
                    )

            if blocked_pending:
                self._retain_pending_street_boundary(
                    observation,
                    action_order=action_order,
                    board=observed_board,
                    complete_pending=complete_pending,
                )
                return ()

            for seat in pending:
                action = (
                    self.hand
                    .observe_no_commitment(
                        seat
                    )
                )

                completion = {
                    "frame":
                        observation.get("frame"),
                    "type":
                        "STREET_BOUNDARY_COMPLETION",
                    "street":
                        self.hand.street,
                    "seat": seat,
                    "proved_by":
                        boundary_type,
                    "semantic_action":
                        action,
                }

                self.events.append(
                    completion
                )
                emitted.append(
                    completion
                )

            if self.hand.next_actor is not None:
                raise ValueError(
                    "boundary completion did not "
                    "close prior street: "
                    f"street={self.hand.street} "
                    f"next_actor={self.hand.next_actor}"
                )

        self.hand.start_street(
            street,
            list(action_order),
            board=observed_board,
        )

        admitted = {
            "frame":
                observation.get("frame"),
            "type":
                "STREET_BOUNDARY_ADMITTED",
            "physical_type":
                boundary_type,
            "street": street,
            "board_count":
                board_count,
            "board":
                list(self.hand.board),
            "next_actor":
                self.hand.next_actor,
        }

        self.events.append(admitted)
        emitted.append(admitted)

        self._publish_if_changed(
            observation.get("frame")
        )

        return tuple(emitted)

    def snapshot(self) -> Dict[str, Any]:
        """
        Read-only diagnostic view of observer-owned state.
        """

        return {
            "street": self.hand.street,
            "next_actor":
                self.hand.next_actor,
            "trusted_stacks":
                dict(self.trusted_stacks),
            "opponent_seats":
                list(self.opponent_seats),
            "quantitative_seats":
                list(
                    self.quantitative_seats
                ),
            "quantitative_retry_pending":
                {
                    seat: dict(state)
                    for seat, state
                    in self.quantitative_retry_pending.items()
                },
            "quantitative_confirmation_pending":
                {
                    seat: dict(state)
                    for seat, state
                    in self.quantitative_confirmation_pending.items()
                },
            "pending_quantitative_evidence":
                [
                    dict(row)
                    for row
                    in self.pending_quantitative_evidence
                ],
            "pending_card_disappearances":
                [
                    dict(row)
                    for row
                    in self.pending_card_disappearances
                ],
            "pending_street_boundaries":
                [
                    {
                        "observation":
                            dict(
                                row["observation"]
                            ),
                        "action_order":
                            list(
                                row["action_order"]
                            ),
                        "board":
                            list(
                                row["board"]
                            ),
                        "complete_pending":
                            bool(
                                row[
                                    "complete_pending"
                                ]
                            ),
                    }
                    for row
                    in self.pending_street_boundaries
                ],
            "hero_seat":
                self.hero_seat,
            "action_count":
                len(self.hand.actions),
            "event_count":
                len(self.events),
            "publication_count":
                len(self.publications),
        }

    def observe_bet_regions(
        self,
        frame,
    ):
        """
        Observe native-resolution per-seat chip occupancy.

        This method owns only physical evidence. It never assigns
        CALL/BET/RAISE/ALL_IN and never mutates HandEngine.
        """

        regions = self.geometry.get(
            "bet_regions",
            {},
        )

        if not regions:
            self.confirmed_bet_regions = set()
            return {}

        if not self.bet_region_baseline_initialized:
            self.bet_region_baseline.reset()
            self.bet_region_tracker.reset()

            for seat, rect in regions.items():
                self.bet_region_baseline.capture(
                    f"bet_region:{seat}",
                    frame,
                    rect,
                )

            self.bet_region_baseline_initialized = True
            self.confirmed_bet_regions = set()

            return {}

        raw = bet_region_occupancy(
            frame,
            self.geometry,
            baseline=self.bet_region_baseline,
        )

        tracked = self.bet_region_tracker.update(
            raw
        )

        self.confirmed_bet_regions = {
            seat
            for seat, info in tracked.items()
            if bool(info.get("occupied"))
        }

        for seat, info in tracked.items():
            if info.get("appeared"):
                print(
                    "[BET_REGION_APPEARED]",
                    f"seat={seat}",
                    f"duration_ms="
                    f"{info.get('occupied_duration_ms')}",
                    flush=True,
                )

            if info.get("cleared"):
                print(
                    "[BET_REGION_CLEARED]",
                    f"seat={seat}",
                    flush=True,
                )

                rect = regions.get(seat)

                if rect is not None:
                    self.bet_region_baseline.capture(
                        f"bet_region:{seat}",
                        frame,
                        rect,
                    )

        return tracked

    def process_frame(
        self,
        frame,
        frame_id,
        timestamp=None,
        sensor_frame=None,
        sensor_geometry=None,
    ) -> FrameObservationResult:
        """
        Process one physical frame.

        G3.2 owns cheap card visibility only.

        These are objective physical observations. This lane deliberately
        does not mutate HandEngine and does not assign poker semantics.
        """

        # Two explicit perception lanes:
        #
        # frame / self.geometry:
        #   quantitative native-resolution stack perception.
        #
        # sensor_frame / sensor_geometry:
        #   established card and board physical sensors.
        #
        # Replay callers omit these arguments and preserve the
        # historical single-frame behavior.
        physical_frame = (
            frame
            if sensor_frame is None
            else sensor_frame
        )
        physical_geometry = (
            self.geometry
            if sensor_geometry is None
            else sensor_geometry
        )

        frame_events = []

        # ----------------------------------------------------
        # Objective physical board/street boundary perception.
        #
        # This lane observes only board-card count transitions.
        # It does not advance HandEngine, assign board identity,
        # or complete poker chronology.
        # ----------------------------------------------------
        board_count = int(
            count_board_cards(
                physical_frame,
                physical_geometry,
            )
        )

        previous_board_count = (
            self.previous_board_count
        )

        boundary_type = None

        if previous_board_count is not None:
            if (
                previous_board_count < 3
                and board_count >= 3
            ):
                boundary_type = (
                    "FLOP_BOUNDARY_PHYSICAL"
                )
            elif (
                previous_board_count < 4
                and board_count >= 4
            ):
                boundary_type = (
                    "TURN_BOUNDARY_PHYSICAL"
                )
            elif (
                previous_board_count < 5
                and board_count >= 5
            ):
                boundary_type = (
                    "RIVER_BOUNDARY_PHYSICAL"
                )

        if boundary_type is not None:
            frame_events.append(
                {
                    "frame": frame_id,
                    "type": boundary_type,
                    "board_count": board_count,
                    "previous_board_count":
                        previous_board_count,
                }
            )

        visibility = {}

        for seat in self.opponent_seats:
            regions = (
                physical_geometry
                .get(
                    "hole_cards",
                    {},
                )
                .get(seat)
            )

            if not regions:
                continue

            visible = bool(
                opponent_cards_visible(
                    physical_frame,
                    regions,
                )
            )

            visibility[seat] = visible

            before = (
                self.previous_visibility
                .get(seat)
            )

            if (
                before is True
                and visible is False
            ):
                frame_events.append(
                    {
                        "frame": frame_id,
                        "type":
                            "OPPONENT_CARDS_DISAPPEARED",
                        "seat": seat,
                    }
                )

        hero_visible = bool(
            hero_cards_visible(
                physical_frame,
                physical_geometry,
            )
        )

        # Objective Hero action-button visibility.
        #
        # The canonical sensor lane was validated live:
        #   ABSENT -> VISIBLE when Hero became actionable
        #   VISIBLE -> ABSENT after Hero action completion.
        #
        # These events remain physical evidence only.
        # Some deterministic unit fixtures intentionally provide
        # minimal geometry with no Hero action-button region.
        # Absence of that optional physical sensor means "no button
        # observation", not a malformed poker frame.
        if physical_geometry.get("action_buttons"):
            action_buttons_are_visible = bool(
                action_buttons_visible(
                    physical_frame,
                    physical_geometry,
                )
            )
        else:
            action_buttons_are_visible = False

        previous_action_buttons_visible = (
            self.previous_action_buttons_visible
        )

        if (
            previous_action_buttons_visible
            is not None
            and action_buttons_are_visible
            != previous_action_buttons_visible
        ):
            if action_buttons_are_visible:
                frame_events.append(
                    {
                        "frame": frame_id,
                        "type":
                            "HERO_ACTION_BUTTONS_APPEARED",
                        "seat":
                            self.hero_seat,
                    }
                )
            else:
                frame_events.append(
                    {
                        "frame": frame_id,
                        "type":
                            "HERO_ACTION_BUTTONS_DISAPPEARED",
                        "seat":
                            self.hero_seat,
                    }
                )

        if (
            self.previous_hero_cards_visible
            is True
            and hero_visible is False
        ):
            frame_events.append(
                {
                    "frame": frame_id,
                    "type":
                        "HERO_CARDS_DISAPPEARED_PHYSICAL",
                    "seat":
                        self.hero_seat,
                }
            )

        # ----------------------------------------------------
        # Native-resolution physical chip occupancy.
        #
        # This must run before quantitative settlement evidence is
        # consumed by the live runner so same-frame commitment
        # state is available at the settlement boundary.
        # ----------------------------------------------------

        self.observe_bet_regions(
            frame,
        )

        # ----------------------------------------------------
        # Cheap stack motion -> targeted OCR -> prior-aware
        # quantitative resolution.
        #
        # G3.4A remains perception-only. A positive delta is an
        # objective quantitative observation, not permission to
        # mutate HandEngine.
        # ----------------------------------------------------

        if self.previous_frame is not None:
            for seat in self.quantitative_seats:
                if seat not in self.trusted_stacks:
                    continue

                motion = measure_stack_motion(
                    self.previous_frame,
                    frame,
                    self.geometry,
                    seat,
                )

                retry_state = (
                    self.quantitative_retry_pending
                    .get(seat)
                )

                confirmation_state = (
                    self.quantitative_confirmation_pending
                    .get(seat)
                )

                confirmation_owned = bool(
                    confirmation_state is not None
                    and int(
                        confirmation_state.get(
                            "attempts",
                            0,
                        )
                    )
                    < self.quantitative_confirmation_max_attempts
                    and frame_id
                    != confirmation_state.get(
                        "first_frame"
                    )
                )

                retry_owned = bool(
                    retry_state is not None
                    and int(
                        retry_state.get(
                            "attempts",
                            0,
                        )
                    )
                    < self.quantitative_retry_max_attempts
                )

                if retry_state is not None:
                    if seat in self.confirmed_bet_regions:
                        retry_state[
                            "commitment_seen"
                        ] = True

                    elif retry_state.get(
                        "commitment_seen",
                        False,
                    ):
                        # Commitment was independently confirmed
                        # and has now disappeared. This physical
                        # transition no longer owns retry work.
                        self.quantitative_retry_pending.pop(
                            seat,
                            None,
                        )
                        retry_state = None
                        retry_owned = False

                if (
                    not motion.wake
                    and not retry_owned
                    and not confirmation_owned
                ):
                    continue

                prior = self.trusted_stacks[
                    seat
                ]

                reading = self.stack_reader(
                    self._stack_crop(
                        frame,
                        seat,
                    )
                )

                resolution = (
                    resolve_fast_stack(
                        reading,
                        prior,
                    )
                )

                if resolution.resolved:
                    if retry_state is not None:
                        print(
                            "[QUANTITATIVE_RETRY_RESOLVED]",
                            f"frame={frame_id}",
                            f"seat={seat}",
                            f"value={resolution.value}",
                            f"attempts="
                            f"{retry_state.get('attempts', 0)}",
                            flush=True,
                        )

                    self.quantitative_retry_pending.pop(
                        seat,
                        None,
                    )

                elif (
                    motion.wake
                    or retry_state is not None
                ):
                    # The physical stack-motion wake owns the
                    # unresolved transition immediately.
                    #
                    # Bet-region confirmation may arrive one frame
                    # later because that sensor is intentionally
                    # debounced. Do not consume the quantitative
                    # wake while waiting for that independent
                    # physical evidence.
                    previous_attempts = int(
                        (
                            retry_state
                            or {}
                        ).get(
                            "attempts",
                            0,
                        )
                    )

                    attempts = previous_attempts + 1

                    if (
                        attempts
                        < self.quantitative_retry_max_attempts
                    ):
                        self.quantitative_retry_pending[
                            seat
                        ] = {
                            "attempts": attempts,
                            "first_frame": (
                                (
                                    retry_state
                                    or {}
                                ).get(
                                    "first_frame",
                                    frame_id,
                                )
                            ),
                            "last_frame": frame_id,
                            "commitment_seen": bool(
                                (
                                    retry_state
                                    or {}
                                ).get(
                                    "commitment_seen",
                                    False,
                                )
                                or seat
                                in self.confirmed_bet_regions
                            ),
                        }

                        print(
                            "[QUANTITATIVE_RETRY_ARMED]",
                            f"frame={frame_id}",
                            f"seat={seat}",
                            f"attempt={attempts}",
                            f"commitment="
                            f"{seat in self.confirmed_bet_regions}",
                            flush=True,
                        )

                    else:
                        self.quantitative_retry_pending.pop(
                            seat,
                            None,
                        )

                        print(
                            "[QUANTITATIVE_RETRY_EXHAUSTED]",
                            f"frame={frame_id}",
                            f"seat={seat}",
                            f"attempts={attempts}",
                            flush=True,
                        )

                if (
                    resolution.resolved
                    and resolution.value is not None
                ):
                    resolved_value = float(
                        resolution.value
                    )

                    changed_value = bool(
                        resolved_value
                        < float(prior) - 0.01
                    )

                    if confirmation_state is not None:
                        expected_value = float(
                            confirmation_state[
                                "value"
                            ]
                        )

                        if (
                            abs(
                                resolved_value
                                - expected_value
                            )
                            <= 0.01
                        ):
                            print(
                                "[QUANTITATIVE_CONFIRMATION_OBSERVED]",
                                f"frame={frame_id}",
                                f"seat={seat}",
                                f"value={resolved_value}",
                                flush=True,
                            )

                            self.quantitative_confirmation_pending.pop(
                                seat,
                                None,
                            )

                        else:
                            attempts = int(
                                confirmation_state.get(
                                    "attempts",
                                    0,
                                )
                            ) + 1

                            if (
                                attempts
                                < self.quantitative_confirmation_max_attempts
                            ):
                                confirmation_state[
                                    "attempts"
                                ] = attempts
                                confirmation_state[
                                    "last_frame"
                                ] = frame_id
                            else:
                                self.quantitative_confirmation_pending.pop(
                                    seat,
                                    None,
                                )

                                print(
                                    "[QUANTITATIVE_CONFIRMATION_EXHAUSTED]",
                                    f"frame={frame_id}",
                                    f"seat={seat}",
                                    flush=True,
                                )

                    elif changed_value:
                        self.quantitative_confirmation_pending[
                            seat
                        ] = {
                            "value": resolved_value,
                            "first_frame": frame_id,
                            "last_frame": frame_id,
                            "attempts": 0,
                        }

                        print(
                            "[QUANTITATIVE_CONFIRMATION_ARMED]",
                            f"frame={frame_id}",
                            f"seat={seat}",
                            f"value={resolved_value}",
                            flush=True,
                        )

                event = {
                    "frame": frame_id,
                    "type":
                        "STACK_QUANTITATIVE_OBSERVATION",
                    "seat": seat,
                    "prior": prior,
                    "reader_value":
                        reading.get(
                            "stack_bb"
                        ),
                    "resolved":
                        resolution.resolved,
                    "resolved_value":
                        resolution.value,
                    "candidates":
                        tuple(
                            resolution.candidates
                        ),
                    "confidence":
                        float(
                            reading.get(
                                "confidence"
                            )
                            or 0.0
                        ),
                    "votes":
                        int(
                            reading.get(
                                "votes"
                            )
                            or 0
                        ),
                    "mode":
                        reading.get(
                            "mode"
                        ),
                }

                if (
                    resolution.resolved
                    and resolution.value
                    is not None
                ):
                    value = float(
                        resolution.value
                    )

                    event[
                        "physical_delta_bb"
                    ] = round(
                        prior - value,
                        2,
                    )

                frame_events.append(
                    event
                )

        self.previous_visibility = (
            visibility
        )

        self.previous_hero_cards_visible = (
            hero_visible
        )

        self.previous_action_buttons_visible = (
            action_buttons_are_visible
        )

        self.previous_board_count = board_count

        self.previous_frame = frame

        self.events.extend(
            frame_events
        )

        return FrameObservationResult(
            frame_id=frame_id,
            events=tuple(
                frame_events
            ),
            changed=False,
            text=None,
        )
