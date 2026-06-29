from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DetectionResult:
    found: bool
    confidence: float
    value: Any = None
    debug_image: Optional[str] = None
    message: str = ""
