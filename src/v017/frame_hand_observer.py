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
    hero_cards_visible,
    opponent_cards_visible,
)

from src.v017.hand_engine import (
    HandEngine,
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

        self.previous_text: Optional[str] = (
            None
        )

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

        self.previous_visibility = (
            visibility
        )

        self.previous_hero_cards_visible = (
            hero_visible
        )

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
