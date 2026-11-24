"""POST /api/screening/score: plate answers -> CVDProfile. Author: Iris.

Scoring itself is Avneet's chromafix.screening.scoring.score (CLAUDE.md Section 6). Until
that module exists this endpoint responds 503.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from chromafix.profile import CVDProfile
from chromafix.screening import Plate
from server.routes.plates import load_plates, plates_dir
from server.schemas import ProfileJSON

router = APIRouter()

# Plain int: Starlette renamed this constant between versions.
UNPROCESSABLE = 422

ScoreFn = Callable[[list[dict], dict[str, Plate]], CVDProfile]


class PlateAnswer(BaseModel):
    """One answer: the digit the participant read, or "none"."""

    model_config = ConfigDict(extra="forbid")

    plate_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    answer: str = Field(pattern=r"^([0-9]|none)$")


class ScoreRequest(BaseModel):
    """Body of POST /api/screening/score."""

    model_config = ConfigDict(extra="forbid")

    answers: list[PlateAnswer] = Field(min_length=1, max_length=200)


def score_function() -> ScoreFn:
    """chromafix.screening.scoring.score, or 503 if it is not available yet. Overridden in tests."""
    try:
        from chromafix.screening.scoring import score
    except ImportError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "screening scoring is not available yet"
        ) from error
    return score


@router.post("/screening/score")
def post_score(
    body: ScoreRequest,
    directory: Annotated[Path, Depends(plates_dir)],
    score: Annotated[ScoreFn, Depends(score_function)],
) -> ProfileJSON:
    """Score the answers against the plates they refer to."""
    plates = load_plates(directory)
    unknown = sorted({a.plate_id for a in body.answers} - plates.keys())
    if unknown:
        raise HTTPException(UNPROCESSABLE, f"unknown plates: {unknown}")
    answers = [a.model_dump() for a in body.answers]
    profile = score(answers, {a["plate_id"]: plates[a["plate_id"]] for a in answers})
    return ProfileJSON.model_validate(profile.to_dict())
