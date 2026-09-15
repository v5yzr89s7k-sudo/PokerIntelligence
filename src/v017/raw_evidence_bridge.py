from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RawEvidence:
    """
    Objective perception evidence delivered to HandEngine.

    This layer may identify:
        - physical seat
        - card disappearance
        - measured stack commitment

    It MUST NOT identify:
        - fold
        - call
        - bet
        - raise

    Poker semantics belong exclusively to HandEngine.
    """

    sequence: int
    frame: int
    seat: str
    evidence_type: str
    delta_bb: Optional[float] = None


class RawEvidenceBridge:
    """
    Thin perception -> HandEngine adapter.

    No poker action inference is permitted here.
    """

    CARDS_DISAPPEARED = "CARDS_DISAPPEARED"
    STACK_COMMITMENT = "STACK_COMMITMENT"

    def __init__(self, hand_engine):
        self.hand_engine = hand_engine
        self.evidence = []

    def submit_cards_disappeared(
        self,
        frame,
        seat,
    ):
        item = RawEvidence(
            sequence=len(self.evidence) + 1,
            frame=int(frame),
            seat=seat,
            evidence_type=self.CARDS_DISAPPEARED,
        )

        self.evidence.append(item)

        self.hand_engine.observe_cards_disappeared(
            seat
        )

        return item

    def submit_stack_commitment(
        self,
        frame,
        seat,
        delta_bb,
    ):
        delta_bb = float(delta_bb)

        if delta_bb <= 0:
            raise ValueError(
                "stack commitment must be positive: "
                f"seat={seat} delta_bb={delta_bb}"
            )

        item = RawEvidence(
            sequence=len(self.evidence) + 1,
            frame=int(frame),
            seat=seat,
            evidence_type=self.STACK_COMMITMENT,
            delta_bb=delta_bb,
        )

        self.evidence.append(item)

        action = (
            self.hand_engine.observe_stack_commitment(
                seat,
                delta_bb,
            )
        )

        return item, action

    def observations(self):
        return [
            {
                "sequence": item.sequence,
                "frame": item.frame,
                "seat": item.seat,
                "evidence_type": item.evidence_type,
                "delta_bb": item.delta_bb,
            }
            for item in self.evidence
        ]
