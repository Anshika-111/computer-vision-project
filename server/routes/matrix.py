"""GET /api/matrix: 3x3 simulation or recoloring matrix for live mode. Author: Iris.

The matrix is row-major and acts on linear RGB column vectors (out_px = M @ in_px),
exactly as chromafix returns it (CLAUDE.md Section 5). The client transposes it for
GLSL (Section 8).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from chromafix.profile import CVDProfile
from chromafix.recolor import recolor_matrix
from chromafix.simulate import simulation_matrix
from server.schemas import CVDTypeName, MethodName

router = APIRouter()

Row = tuple[float, float, float]


class MatrixQuery(BaseModel):
    """Query string of GET /api/matrix."""

    # Reject unknown parameters so a typo like `severty=0.6` fails loudly
    # instead of silently returning a matrix for the wrong request.
    model_config = ConfigDict(extra="forbid")

    mode: Literal["simulate", "recolor"]
    type: CVDTypeName
    severity: float = Field(ge=0.0, le=1.0)
    method: MethodName | None = Field(
        default=None, description="Required for mode=recolor; not allowed for mode=simulate."
    )

    @model_validator(mode="after")
    def _check_combination(self) -> "MatrixQuery":
        if self.type == "normal" and self.severity != 0.0:
            raise ValueError("severity must be 0.0 when type is 'normal'")
        if self.mode == "simulate" and self.method is not None:
            raise ValueError("method only applies to mode=recolor")
        if self.mode == "recolor" and self.method is None:
            raise ValueError("mode=recolor needs a method")
        if self.method == "neural":
            raise ValueError("'neural' has no matrix form; use POST /api/recolor")
        return self


class MatrixResponse(BaseModel):
    """A row-major 3x3 matrix acting on linear RGB column vectors."""

    matrix: tuple[Row, Row, Row]


@router.get("/matrix")
def get_matrix(query: Annotated[MatrixQuery, Query()]) -> MatrixResponse:
    """Return the simulation matrix S or the recoloring matrix R.

    Raises 503 for a method that exists but is not ready yet (personalized before tuning),
    matching how /api/recolor reports an unavailable neural model.
    """
    if query.mode == "simulate":
        m = simulation_matrix(query.type, query.severity)
    else:
        profile = CVDProfile(type=query.type, severity=query.severity)
        try:
            m = recolor_matrix(profile, query.method)
        except NotImplementedError as error:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return MatrixResponse(matrix=m.tolist())
