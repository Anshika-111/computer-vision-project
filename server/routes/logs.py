"""POST /api/logs: append one study-log trial to results/study/<session_id>.jsonl. Author: Iris."""

import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[2]

# Identifiers become part of a file name or are joined on later, so keep them to a safe charset.
SafeId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]

_write_lock = threading.Lock()


class ProfileJSON(BaseModel):
    """JSON form of a CVDProfile (CLAUDE.md Section 6)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["normal", "protan", "deutan", "tritan"]
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _normal_has_zero_severity(self) -> "ProfileJSON":
        if self.type == "normal" and self.severity != 0.0:
            raise ValueError("severity must be 0.0 when type is 'normal'")
        return self


class StudyLog(BaseModel):
    """One trial of a mini-game study (CLAUDE.md Section 7).

    Unknown fields are rejected so that names, emails, or other personal data
    cannot end up in the logs by accident.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: SafeId
    participant_id: Annotated[str, Field(pattern=r"^P\d{1,4}$")]
    profile: ProfileJSON
    game: SafeId
    trial_id: int = Field(ge=0)
    image_id: SafeId
    condition: Literal["none", "fixed", "personalized", "neural"]
    answer: str = Field(max_length=64)
    correct: bool
    rt_ms: int = Field(ge=0)
    timestamp: str

    @field_validator("timestamp")
    @classmethod
    def _timestamp_is_iso_with_timezone(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("timestamp must include a timezone, e.g. 2026-11-20T18:04:11Z")
        return value


def study_dir() -> Path:
    """Directory that holds the study logs. Overridden in tests."""
    return REPO_ROOT / "results" / "study"


@router.post("/logs", status_code=status.HTTP_204_NO_CONTENT)
def post_log(log: StudyLog, directory: Annotated[Path, Depends(study_dir)]) -> Response:
    """Append one trial as a single JSON line to <session_id>.jsonl."""
    line = log.model_dump_json()
    with _write_lock:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{log.session_id}.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
