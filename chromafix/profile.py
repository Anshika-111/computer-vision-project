"""CVDProfile: a user's color vision type, severity, and screening confidence. Author: Avneet."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from chromafix.constants import ALL_TYPES

CVDType = Literal["normal", "protan", "deutan", "tritan"]


@dataclass(frozen=True)
class CVDProfile:
    """A user's color vision profile.

    JSON form: {"type": "deutan", "severity": 0.6, "confidence": 0.8}

    Attributes:
        type: "normal", "protan", "deutan", or "tritan".
        severity: 0.0–1.0. Always 0.0 when type == "normal".
        confidence: 0.0–1.0, how consistent the screening answers were.
    """

    type: CVDType
    severity: float
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.type not in ALL_TYPES:
            raise ValueError(f"type must be one of {ALL_TYPES}, got {self.type!r}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError(f"severity must be in [0, 1], got {self.severity}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.type == "normal" and self.severity != 0.0:
            raise ValueError("severity must be 0.0 when type is 'normal'")
        object.__setattr__(self, "severity", float(self.severity))
        object.__setattr__(self, "confidence", float(self.confidence))

    def to_dict(self) -> dict:
        """Return the JSON-ready dict form."""
        return {"type": self.type, "severity": self.severity, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, d: dict) -> CVDProfile:
        """Build a profile from its dict form. `confidence` is optional (defaults to 1.0)."""
        return cls(
            type=d["type"],
            severity=float(d["severity"]),
            confidence=float(d.get("confidence", 1.0)),
        )

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> CVDProfile:
        """Parse a profile from a JSON string."""
        return cls.from_dict(json.loads(s))

    @classmethod
    def normal(cls) -> CVDProfile:
        """Profile for typical color vision."""
        return cls(type="normal", severity=0.0, confidence=1.0)
