"""POST /api/simulate and POST /api/recolor: process an uploaded image, return a PNG. Author: Iris.

Uploads are processed in memory and never written to disk (CLAUDE.md Section 8).
"""

from typing import Annotated

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import TypeAdapter, ValidationError

from chromafix.profile import CVDProfile
from chromafix.recolor import NeuralModelUnavailable, recolor
from chromafix.simulate import simulate
from server.imageio import BadImage, decode_upload, encode_png
from server.schemas import MethodName, ProfileJSON

router = APIRouter()

# Plain int: Starlette renamed this constant between versions.
UNPROCESSABLE = 422

PNG_RESPONSE = {200: {"content": {"image/png": {}}, "description": "PNG image (sRGB)"}}

_method_adapter: TypeAdapter[MethodName] = TypeAdapter(MethodName)


def _parse_profile(raw: str) -> CVDProfile:
    """Parse the multipart `profile` field (CVDProfile JSON form) or raise 422."""
    try:
        parsed = ProfileJSON.model_validate_json(raw)
    except ValidationError as error:
        raise HTTPException(UNPROCESSABLE, f"invalid profile: {error}") from error
    return CVDProfile.from_dict(parsed.model_dump())


def _parse_method(raw: str) -> MethodName:
    """Validate the multipart `method` field or raise 422."""
    try:
        return _method_adapter.validate_python(raw)
    except ValidationError as error:
        raise HTTPException(UNPROCESSABLE, f"invalid method: {raw!r}") from error


def _read_image(upload: UploadFile) -> np.ndarray:
    """Decode the upload to a linear image or raise 422."""
    try:
        return decode_upload(upload.file.read())
    except BadImage as error:
        raise HTTPException(UNPROCESSABLE, str(error)) from error


def _png(img: np.ndarray) -> Response:
    # no-store: the browser and any proxy should not keep the user's image either.
    return Response(encode_png(img), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/simulate", response_class=Response, responses=PNG_RESPONSE)
def post_simulate(
    image: Annotated[UploadFile, File(description="sRGB image file")],
    profile: Annotated[str, Form(description='CVDProfile JSON, e.g. {"type":"deutan",...}')],
) -> Response:
    """Return the image as a viewer with `profile` would see it (Machado 2009)."""
    cvd = _parse_profile(profile)
    img = _read_image(image)
    return _png(simulate(img, cvd.type, cvd.severity))


@router.post("/recolor", response_class=Response, responses=PNG_RESPONSE)
def post_recolor(
    image: Annotated[UploadFile, File(description="sRGB image file")],
    profile: Annotated[str, Form(description="CVDProfile JSON")],
    method: Annotated[str, Form(description="none | fixed | personalized | neural")],
) -> Response:
    """Return the image recolored for `profile` with `method`.

    Responds 503 when the method exists but is not ready on this server (neural model
    missing, or personalized parameters not tuned yet).
    """
    cvd = _parse_profile(profile)
    name = _parse_method(method)
    img = _read_image(image)
    try:
        out = recolor(img, cvd, name)
    except (NeuralModelUnavailable, NotImplementedError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    return _png(out)
