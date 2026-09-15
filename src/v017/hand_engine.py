from dataclasses import dataclass, field
from typing import Dict, List, Optional


EPSILON = 0.02


@dataclass
class PlayerState:
    seat: str
    position: str
    name: str
    starting_stack_bb: float

    folded: bool = False
    street_commitment_bb: float = 0.0


@dataclass
class HandAction:
    sequence: int
    street: str
    seat: str
    position: str
    name: str
    action: str

    amount_bb: Optional[float] = None
    raise_to_bb: Optional[float] = None


class HandEngine:
    """
    V0.17 single semantic authority.

    This object alone owns:
        action chronology
        folded state
        street commitments
        current betting price
        next actor
        semantic actions

    Perception supplies observations.
    Perception does not decide poker actions.
    """

    def __init__(
        self,
        players,
        action_order,
        small_blind_seat,
        big_blind_seat,
        small_blind_bb=0.5,
        big_blind_bb=1.0,
    ):
        self.street = "PREFLOP"

        self.players: Dict[str, PlayerState] = {
            item["seat"]: PlayerState(
                seat=item["seat"],
                position=item["position"],
                name=item["name"],
                starting_stack_bb=float(
                    item["stack_bb"]
                ),
            )
            for item in players
        }

        self.action_order = list(action_order)
        self.actor_index = 0

        self.current_price_bb = float(
            big_blind_bb
        )

        self.actions: List[HandAction] = []

        self._post_blind(
            small_blind_seat,
            float(small_blind_bb),
            "POST_SMALL_BLIND",
        )

        self._post_blind(
            big_blind_seat,
            float(big_blind_bb),
            "POST_BIG_BLIND",
        )

    @property
    def next_actor(self):
        if self.actor_index >= len(
            self.action_order
        ):
            return None

        return self.action_order[
            self.actor_index
        ]

    def _append_action(
        self,
        seat,
        action,
        amount_bb=None,
        raise_to_bb=None,
    ):
        player = self.players[seat]

        self.actions.append(
            HandAction(
                sequence=len(self.actions) + 1,
                street=self.street,
                seat=seat,
                position=player.position,
                name=player.name,
                action=action,
                amount_bb=amount_bb,
                raise_to_bb=raise_to_bb,
            )
        )

    def _post_blind(
        self,
        seat,
        amount_bb,
        action,
    ):
        player = self.players[seat]

        player.street_commitment_bb = (
            amount_bb
        )

        self._append_action(
            seat,
            action,
            amount_bb=amount_bb,
        )

    def _require_actor(self, seat):
        expected = self.next_actor

        if seat != expected:
            raise ValueError(
                "chronology violation: "
                f"observed={seat} "
                f"expected={expected}"
            )

    def _advance_actor(self):
        self.actor_index += 1

    def observe_cards_disappeared(
        self,
        seat,
    ):
        self._require_actor(seat)

        player = self.players[seat]

        if player.folded:
            raise ValueError(
                f"duplicate fold: {seat}"
            )

        player.folded = True

        self._append_action(
            seat,
            "FOLD",
        )

        self._advance_actor()

    def observe_stack_commitment(
        self,
        seat,
        delta_bb,
    ):
        """
        delta_bb is the newly observed chip decrease attributable
        to the current street.

        HandEngine converts that objective measurement into poker
        semantics using its own authoritative commitment/price state.
        """

        self._require_actor(seat)

        delta_bb = float(delta_bb)

        if delta_bb <= 0:
            raise ValueError(
                f"invalid commitment delta: {delta_bb}"
            )

        player = self.players[seat]

        prior = float(
            player.street_commitment_bb
        )

        target = prior + delta_bb
        price = float(
            self.current_price_bb
        )

        if target > price + EPSILON:
            action = "RAISE"

            player.street_commitment_bb = (
                target
            )

            self.current_price_bb = target

            self._append_action(
                seat,
                action,
                raise_to_bb=target,
            )

        elif abs(
            target - price
        ) <= EPSILON:
            action = "CALL"

            player.street_commitment_bb = (
                target
            )

            self._append_action(
                seat,
                action,
                amount_bb=delta_bb,
            )

        else:
            # Short commitment is only legal here as an all-in.
            # Milestone A deliberately does not infer all-in status
            # without explicit evidence.
            raise ValueError(
                "commitment below current price "
                "without all-in evidence: "
                f"seat={seat} "
                f"prior={prior} "
                f"delta={delta_bb} "
                f"target={target} "
                f"price={price}"
            )

        self._advance_actor()

        return action

    def semantic_actions(self):
        return [
            {
                "sequence": item.sequence,
                "street": item.street,
                "seat": item.seat,
                "position": item.position,
                "name": item.name,
                "action": item.action,
                "amount_bb": item.amount_bb,
                "raise_to_bb": item.raise_to_bb,
            }
            for item in self.actions
        ]
