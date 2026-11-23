"""Request and response models shared by several API routes. Author: Iris."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Spelled out (not built from chromafix.constants) so FastAPI can list them in the API docs;
# tests/test_server_schemas.py checks that they stay equal to the constants.
CVDTypeName = Literal["normal", "protan", "deutan", "tritan"]
MethodName = Literal["none", "fixed", "personalized", "neural"]


class ProfileJSON(BaseModel):
    """JSON form of a CVDProfile (CLAUDE.md Section 6)."""

    model_config = ConfigDict(extra="forbid")

    type: CVDTypeName
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _normal_has_zero_severity(self) -> "ProfileJSON":
        if self.type == "normal" and self.severity != 0.0:
            raise ValueError("severity must be 0.0 when type is 'normal'")
        return self
