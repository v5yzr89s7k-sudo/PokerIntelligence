"""
Player identity subsystem.

This package owns decisions about who occupies a physical poker seat.
It does not own stacks, dealer detection, positions, board state, or
canonical hand state.
"""

from src.identity.identity_manager import IdentityManager
from src.identity.identity_record import IdentityRecord

__all__ = [
    "IdentityManager",
    "IdentityRecord",
]
