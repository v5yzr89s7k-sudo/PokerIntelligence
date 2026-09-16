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
from src.v017.stack_motion_gate import (
    measure_stack_motion,
)


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
    ):
        self.geometry = geometry
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

        # Physical perception baseline only.
        # This is not authoritative poker street state.
        self.previous_board_count: Optional[int] = (
            None
        )

        self.previous_text: Optional[str] = (
            None
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
        It may mutate the hand only when `seat` is the authoritative
        next actor.

        Returns the semantic action when admitted, otherwise None.
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

    def admit_quantitative_observation(
        self,
        observation: Dict[str, Any],
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
            return ()

        if not observation.get("resolved"):
            return ()

        value = observation.get(
            "resolved_value"
        )

        if value is None:
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
            return ()

        # Old observations cannot replay an already-consumed actor.
        if seat not in self.hand.pending_to_act:
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

        action = (
            self.hand
            .observe_stack_commitment(
                seat,
                measurement.normalized_delta_bb,
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
        if street != expected_street:
            return ()

        observed_board = list(board)

        if len(observed_board) != expected_count:
            raise ValueError(
                "board identity length does not "
                "match physical boundary: "
                f"street={street} "
                f"cards={len(observed_board)} "
                f"expected={expected_count}"
            )

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
                return ()

            pending = list(
                self.hand.pending_to_act
            )

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
            "hero_seat":
                self.hero_seat,
            "action_count":
                len(self.hand.actions),
            "event_count":
                len(self.events),
            "publication_count":
                len(self.publications),
        }

    def process_frame(
        self,
        frame,
        frame_id,
        timestamp=None,
    ) -> FrameObservationResult:
        """
        Process one physical frame.

        G3.2 owns cheap card visibility only.

        These are objective physical observations. This lane deliberately
        does not mutate HandEngine and does not assign poker semantics.
        """

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
                frame,
                self.geometry,
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
                self.geometry
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
                    frame,
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
                frame,
                self.geometry,
            )
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

                if not motion.wake:
                    continue

                prior = self.trusted_stacks[
                    seat
                ]

                reading = read_stack(
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
