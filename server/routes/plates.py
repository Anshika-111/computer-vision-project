"""GET /api/plates and GET /api/plates/{plate_id}.png: screening plates. Author: Iris.

Plates are generated offline by scripts/make_plates.py into data/plates/ (PNGs plus
plates.json; not in git, see the team Drive). The browser never receives fail_severity
or the digit, only what Plate.public_dict() exposes.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse

from chromafix.screening import Plate, select_plates

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[2]

PlateId = Annotated[str, PathParam(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


def plates_dir() -> Path:
    """Directory holding plates.json and the plate PNGs. Overridden in tests."""
    return REPO_ROOT / "data" / "plates"


@lru_cache(maxsize=4)
def _load(path: Path, mtime_ns: int) -> dict[str, Plate]:
    # mtime_ns is part of the cache key so regenerating plates.json is picked up.
    del mtime_ns
    data = json.loads(path.read_text(encoding="utf-8"))
    return {d["plate_id"]: Plate.from_dict(d) for d in data}


def load_plates(directory: Path) -> dict[str, Plate]:
    """Validated plates from <directory>/plates.json, keyed by plate_id.

    Raises:
        HTTPException 503: plates.json is missing (plates not generated on this machine).
    """
    path = directory / "plates.json"
    try:
        mtime_ns = path.stat().st_mtime_ns
    except FileNotFoundError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "screening plates not found; run scripts/make_plates.py or copy data/plates/ "
            "from the team Drive",
        ) from error
    return _load(path, mtime_ns)


@router.get("/plates")
def get_plates(
    directory: Annotated[Path, Depends(plates_dir)],
    n: Annotated[int, Query(ge=1, le=200)] = 24,
) -> list[dict]:
    """A balanced set of n plates (controls + every type and difficulty), without answers.

    The selection is deterministic, so every participant sees the same plates in the
    same order.
    """
    plates = load_plates(directory)
    return [p.public_dict() for p in select_plates(list(plates.values()), n=n)]


@router.get(
    "/plates/{plate_id}.png",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_plate_image(
    plate_id: PlateId, directory: Annotated[Path, Depends(plates_dir)]
) -> FileResponse:
    """The plate image. Only ids listed in plates.json are served."""
    if plate_id not in load_plates(directory):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown plate {plate_id!r}")
    path = directory / f"{plate_id}.png"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"image for plate {plate_id!r} missing")
    return FileResponse(path, media_type="image/png")
