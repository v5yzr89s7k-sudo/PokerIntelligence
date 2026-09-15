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
        self.pending_to_act = list(
            self.action_order
        )

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
        if not self.pending_to_act:
            return None

        return self.pending_to_act[0]

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
        if self.pending_to_act:
            self.pending_to_act.pop(0)

    def _reset_pending_after_aggression(
        self,
        aggressor,
    ):
        if aggressor not in self.action_order:
            raise ValueError(
                f"aggressor outside action order: {aggressor}"
            )

        index = self.action_order.index(
            aggressor
        )

        order = (
            self.action_order[index + 1:]
            + self.action_order[:index]
        )

        self.pending_to_act = [
            seat
            for seat in order
            if (
                seat != aggressor
                and not self.players[seat].folded
            )
        ]

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

        return "FOLD"

    def observe_no_commitment(
        self,
        seat,
    ):
        """
        Objective observation that the current actor completed
        action without committing additional chips.

        HandEngine alone determines whether that can mean CHECK.
        """
        self._require_actor(seat)

        player = self.players[seat]

        prior = float(
            player.street_commitment_bb
        )

        price = float(
            self.current_price_bb
        )

        if abs(prior - price) > EPSILON:
            raise ValueError(
                "cannot check while facing a bet: "
                f"seat={seat} "
                f"committed={prior} "
                f"price={price}"
            )

        self._append_action(
            seat,
            "CHECK",
        )

        self._advance_actor()

        return "CHECK"

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
            if (
                self.street != "PREFLOP"
                and price <= EPSILON
            ):
                action = "BET"
            else:
                action = "RAISE"

            player.street_commitment_bb = (
                target
            )

            self.current_price_bb = target

            if action == "BET":
                self._append_action(
                    seat,
                    action,
                    amount_bb=delta_bb,
                )
            else:
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

        if action in {
            "BET",
            "RAISE",
        }:
            self._reset_pending_after_aggression(
                seat
            )
        else:
            self._advance_actor()

        return action

    def start_street(
        self,
        street,
        action_order,
    ):
        """
        Advance the single authoritative hand state to a new street.

        The board transition determines the street boundary.
        Folded state and prior chronology survive.
        Street-local betting state does not.
        """
        street = str(street).upper()

        allowed = {
            "FLOP",
            "TURN",
            "RIVER",
        }

        if street not in allowed:
            raise ValueError(
                f"invalid postflop street: {street}"
            )

        progression = {
            "PREFLOP": "FLOP",
            "FLOP": "TURN",
            "TURN": "RIVER",
        }

        expected = progression.get(self.street)

        if street != expected:
            raise ValueError(
                "street chronology violation: "
                f"current={self.street} "
                f"observed={street} "
                f"expected={expected}"
            )

        order = list(action_order)

        for seat in order:
            if seat not in self.players:
                raise ValueError(
                    f"unknown seat in action order: {seat}"
                )

            if self.players[seat].folded:
                raise ValueError(
                    "folded seat cannot enter new street "
                    f"action order: {seat}"
                )

        self.street = street
        self.action_order = order
        self.pending_to_act = list(order)
        self.current_price_bb = 0.0

        for player in self.players.values():
            player.street_commitment_bb = 0.0

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
