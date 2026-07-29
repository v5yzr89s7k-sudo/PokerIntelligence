from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IdentityRecord:
    """
    Immutable result of resolving one physical seat's player identity.

    This record intentionally contains identity information only.
    Stack values and other table-state measurements belong elsewhere.
    """

    seat: str
    name: str
    source: str
    confidence: Optional[float] = None
    changed: bool = False

    def __post_init__(self):
        seat = str(self.seat or "").strip()
        name = str(self.name or "").strip()
        source = str(self.source or "").strip()

        if not seat:
            raise ValueError("IdentityRecord seat is required")

        if not source:
            raise ValueError("IdentityRecord source is required")

        object.__setattr__(self, "seat", seat)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "source", source)

        if self.confidence is not None:
            confidence = float(self.confidence)

            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    "IdentityRecord confidence must be between 0 and 1"
                )

            object.__setattr__(
                self,
                "confidence",
                confidence,
            )

        object.__setattr__(
            self,
            "changed",
            bool(self.changed),
        )

    @property
    def resolved(self):
        return bool(self.name)

    def to_dict(self):
        return {
            "seat": self.seat,
            "name": self.name,
            "source": self.source,
            "confidence": self.confidence,
            "changed": self.changed,
            "resolved": self.resolved,
        }
