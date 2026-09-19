from dataclasses import dataclass, field
from typing import Dict, List, Optional


EPSILON = 0.02


@dataclass
class PlayerState:
    seat: str
    position: str
    name: str
    starting_stack_bb: Optional[float]

    dealt_in: bool = True
    folded: bool = False
    all_in: bool = False
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
                starting_stack_bb=(
                    None
                    if item.get("stack_bb") is None
                    else float(
                        item["stack_bb"]
                    )
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

        # Objective card observations.
        #
        # HandEngine stores validated card identity but never
        # performs card recognition or card inference.
        self.hero_cards = []
        self.board = []

        # Canonical terminal-result state.
        #
        # Betting closure (next_actor is None) is not sufficient
        # to complete a hand: an all-in hand may still be running
        # out. Result state is established only by an authoritative
        # terminal condition.
        self.hand_complete = False
        self.completion_reason = None
        self.winner_seats = []

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

    def _is_actionable(self, seat):
        player = self.players[seat]
        return (
            player.dealt_in
            and not player.folded
            and not player.all_in
        )

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
                and self._is_actionable(seat)
            )
        ]

    def observe_fold(
        self,
        seat,
    ):
        """
        Record a fold from objective completion evidence.

        The evidence source may differ by actor:
        opponent card disappearance, Hero decision completion,
        or another validated physical observation.

        HandEngine alone owns the FOLD semantic.
        """
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

        # A fold leaving one dealt-in, non-folded player is
        # terminal. No player retains a betting obligation.
        remaining_after_fold = [
            candidate.seat
            for candidate in self.players.values()
            if (
                candidate.dealt_in
                and not candidate.folded
            )
        ]

        if len(remaining_after_fold) == 1:
            self.pending_to_act = []

            # This result requires no winner inference from
            # perception. Once an authoritative FOLD leaves
            # exactly one dealt-in, non-folded player, HandEngine
            # itself owns the uncontested winner.
            self.hand_complete = True
            self.completion_reason = "UNCONTESTED"
            self.winner_seats = [
                remaining_after_fold[0]
            ]

        return "FOLD"

    def unmatched_commitment_bb(
        self,
        seat,
    ):
        """
        Return the objectively unmatched portion of one player's
        current-street commitment.

        This is accounting state only. It does not infer that a refund
        occurred.
        """
        if seat not in self.players:
            raise ValueError(
                f"unknown seat: {seat}"
            )

        player = self.players[seat]

        own = float(
            player.street_commitment_bb
        )

        opponent_commitments = [
            float(
                candidate.street_commitment_bb
            )
            for candidate
            in self.players.values()
            if (
                candidate.seat != seat
                and candidate.dealt_in
            )
        ]

        matched = max(
            opponent_commitments,
            default=0.0,
        )

        return round(
            max(
                0.0,
                own - matched,
            ),
            2,
        )

    def observe_uncalled_return(
        self,
        seat,
        amount_bb,
    ):
        """
        Admit independently observed terminal uncalled-chip return.

        Strict authority contract:

        - the hand must already be complete;
        - completion must be UNCONTESTED;
        - the seat must be the sole authoritative winner;
        - amount must exactly match authoritative unmatched current-
          street commitment within EPSILON.

        This is terminal accounting, not a betting action. It therefore
        does not enter semantic_actions() and cannot reopen chronology.
        """
        if not self.hand_complete:
            raise ValueError(
                "uncalled return requires completed hand"
            )

        if self.completion_reason != "UNCONTESTED":
            raise ValueError(
                "uncalled return requires "
                "UNCONTESTED completion"
            )

        if self.winner_seats != [seat]:
            raise ValueError(
                "uncalled return seat is not "
                "authoritative uncontested winner: "
                f"seat={seat} "
                f"winners={self.winner_seats}"
            )

        amount = round(
            float(amount_bb),
            2,
        )

        if amount <= EPSILON:
            raise ValueError(
                f"invalid uncalled return: {amount}"
            )

        expected = self.unmatched_commitment_bb(
            seat
        )

        if abs(
            amount - expected
        ) > EPSILON:
            raise ValueError(
                "uncalled return does not match "
                "authoritative unmatched commitment: "
                f"seat={seat} "
                f"observed={amount} "
                f"expected={expected}"
            )

        player = self.players[seat]

        player.street_commitment_bb = round(
            max(
                0.0,
                float(
                    player.street_commitment_bb
                )
                - amount,
            ),
            2,
        )

        return amount

    def observe_cards_disappeared(
        self,
        seat,
    ):
        """
        Opponent physical-card disappearance adapter.

        Card perception supplies evidence only; fold semantics remain
        owned by observe_fold().
        """
        return self.observe_fold(
            seat
        )

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
        *,
        all_in_confirmed=False,
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
            # A below-price commitment is legal only with explicit
            # independently confirmed all-in evidence.
            #
            # HandEngine never infers all-in status from stack size.
            if not all_in_confirmed:
                raise ValueError(
                    "commitment below current price "
                    "without all-in evidence: "
                    f"seat={seat} "
                    f"prior={prior} "
                    f"delta={delta_bb} "
                    f"target={target} "
                    f"price={price}"
                )

            action = "CALL"

            player.street_commitment_bb = (
                target
            )

            self._append_action(
                seat,
                action,
                amount_bb=delta_bb,
            )

        if all_in_confirmed:
            player.all_in = True

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

    def observe_hero_cards(
        self,
        cards,
    ):
        """
        Store an already-observed two-card Hero hand.

        Recognition belongs to perception. HandEngine validates and
        owns the accepted objective identity only.
        """
        cards = list(cards)

        if len(cards) != 2:
            raise ValueError(
                "hero cards must contain exactly two cards"
            )

        if len(set(cards)) != 2:
            raise ValueError(
                "hero cards must be distinct"
            )

        if self.hero_cards:
            if cards == self.hero_cards:
                return list(self.hero_cards)

            raise ValueError(
                "hero cards cannot change within a hand"
            )

        if any(
            card in self.board
            for card in cards
        ):
            raise ValueError(
                "hero card duplicates board card"
            )

        self.hero_cards = list(cards)

        return list(self.hero_cards)

    def start_street(
        self,
        street,
        action_order,
        board=None,
    ):
        """
        Advance the single authoritative hand state to a new street.

        The board transition determines the street boundary.
        Folded state and prior chronology survive.
        Street-local betting state does not.
        """
        street = str(street).upper()

        if self.next_actor is not None:
            raise ValueError(
                "cannot advance street while action remains: "
                f"street={self.street} "
                f"next_actor={self.next_actor}"
            )

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

        expected_board_length = {
            "FLOP": 3,
            "TURN": 4,
            "RIVER": 5,
        }[street]

        if board is None:
            # Existing semantic tests may advance streets without
            # card identity. This preserves that contract while
            # ensuring any supplied board is strictly validated.
            next_board = list(self.board)
        else:
            next_board = list(board)

            if len(next_board) != expected_board_length:
                raise ValueError(
                    "board length does not match street: "
                    f"street={street} "
                    f"cards={len(next_board)}"
                )

            if len(set(next_board)) != len(next_board):
                raise ValueError(
                    "board cards must be distinct"
                )

            if any(
                card in self.hero_cards
                for card in next_board
            ):
                raise ValueError(
                    "board duplicates Hero card"
                )

            if (
                self.board
                and next_board[:len(self.board)]
                != self.board
            ):
                raise ValueError(
                    "board history cannot change"
                )

        self.street = street
        self.action_order = order
        self.pending_to_act = [
            seat
            for seat in order
            if self._is_actionable(seat)
        ]
        self.current_price_bb = 0.0

        if board is not None:
            self.board = next_board

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
