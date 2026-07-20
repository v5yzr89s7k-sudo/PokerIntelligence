from dataclasses import dataclass, asdict
from typing import List, Optional

from src.state.canonical_hand import CanonicalHand
from src.state.street_commitment_tracker import StreetCommitmentState


CHECK = "CHECK"
BET = "BET"
FOLD = "FOLD"
CALL = "CALL"
RAISE = "RAISE"


@dataclass
class LegalActionState:
    street: str
    seat: str

    action_due: bool

    legal_actions: List[str]

    current_price_bb: float
    committed_bb: float
    call_amount_bb: float

    betting_open: bool
    owes_response: bool

    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def derive_legal_action_state(
    hand: CanonicalHand,
    street_state: StreetCommitmentState,
    seat: str,
) -> LegalActionState:
    """
    Derive the legal poker actions currently available to one seat.

    This function is deterministic and perception-independent. It does not
    mutate CanonicalHand or StreetCommitmentState.
    """
    street = hand.current_street
    player = hand.players.get(seat)

    current_price = round(
        float(street_state.current_price or 0.0),
        2,
    )

    committed = 0.0

    if player is not None:
        committed = round(
            float(
                player.committed_by_street.get(
                    street,
                    0.0,
                )
                or 0.0
            ),
            2,
        )

    call_amount = round(
        max(
            0.0,
            current_price - committed,
        ),
        2,
    )

    owes_response = (
        seat in street_state.needs_response_from
    )

    if player is None:
        return LegalActionState(
            street=street,
            seat=seat,
            action_due=False,
            legal_actions=[],
            current_price_bb=current_price,
            committed_bb=committed,
            call_amount_bb=call_amount,
            betting_open=bool(street_state.betting_open),
            owes_response=owes_response,
            reason="seat is not present in canonical hand",
        )

    if (
        not player.active
        or player.folded
        or player.all_in
    ):
        return LegalActionState(
            street=street,
            seat=seat,
            action_due=False,
            legal_actions=[],
            current_price_bb=current_price,
            committed_bb=committed,
            call_amount_bb=call_amount,
            betting_open=bool(street_state.betting_open),
            owes_response=owes_response,
            reason="player cannot take further action",
        )

    if street_state.betting_open:
        if not owes_response:
            return LegalActionState(
                street=street,
                seat=seat,
                action_due=False,
                legal_actions=[],
                current_price_bb=current_price,
                committed_bb=committed,
                call_amount_bb=call_amount,
                betting_open=True,
                owes_response=False,
                reason="player does not owe a response to current aggression",
            )

        return LegalActionState(
            street=street,
            seat=seat,
            action_due=True,
            legal_actions=[
                FOLD,
                CALL,
                RAISE,
            ],
            current_price_bb=current_price,
            committed_bb=committed,
            call_amount_bb=call_amount,
            betting_open=True,
            owes_response=True,
            reason="player owes a response to open betting",
        )

    action_due = seat in street_state.pending_to_act

    return LegalActionState(
        street=street,
        seat=seat,
        action_due=action_due,
        legal_actions=(
            [
                CHECK,
                BET,
            ]
            if action_due
            else []
        ),
        current_price_bb=current_price,
        committed_bb=committed,
        call_amount_bb=0.0,
        betting_open=False,
        owes_response=False,
        reason=(
            "player may check or open betting"
            if action_due
            else "player is not currently pending to act"
        ),
    )
