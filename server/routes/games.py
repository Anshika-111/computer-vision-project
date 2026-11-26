"""GET /api/games/{game}/trials and game images: mini-game trials for the demo study. Author: Iris.

Each game is an answer key in server/games/<game>.json. Every entry names a test-split image
and one of its region pairs from data/annotations/pairs.json; the player is asked which of
the two outlined regions (A or B) matches the prompt. Tune-split images are refused, because
the personalized method was tuned on them.

Counterbalancing: answer-key entry k gets condition conds[(k + participant_number) % len(conds)],
so each image rotates through the conditions across consecutive participants. The order the
trials are shown in is shuffled per participant with a seed derived from constants.SEED.
"""

import csv
import json
import random
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chromafix.constants import SEED
from server.routes.methods import available_methods
from server.schemas import MethodName

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[2]

GameName = Annotated[str, PathParam(pattern=r"^[a-z0-9_]{1,32}$")]
ImageId = Annotated[str, PathParam(pattern=r"^[a-z_]+_\d{4}$")]
# Same rule as StudyLog.participant_id in server/routes/logs.py.
ParticipantId = Annotated[str, Query(pattern=r"^P\d{1,4}$")]

Side = Literal["a", "b"]


class GameTrial(BaseModel):
    """One trial: which outlined region (a or b) answers the prompt."""

    trial_id: int
    image_id: str
    pair_id: str
    prompt: str
    options: list[Side]
    correct_answer: Side
    condition: MethodName
    # Polygons in pixel coordinates of the 1024 px dataset image (CLAUDE.md Section 7).
    polygons: dict[Side, list[list[float]]]


def games_dir() -> Path:
    """Directory holding the answer keys (<game>.json). Overridden in tests."""
    return REPO_ROOT / "server" / "games"


def data_dir() -> Path:
    """Repo data directory: manifest.csv, annotations/pairs.json, images/. Overridden in tests."""
    return REPO_ROOT / "data"


def game_conditions() -> list[MethodName]:
    """Conditions used in games: every available method that has a matrix form.

    Neural is left out on purpose: it is slow on a laptop CPU and not trained yet.
    Overridden in tests.
    """
    return [m for m in available_methods() if m != "neural"]


def _manifest(data: Path) -> dict[str, dict[str, str]]:
    with (data / "manifest.csv").open(newline="", encoding="utf-8") as f:
        return {row["image_id"]: row for row in csv.DictReader(f)}


def _pairs(data: Path) -> dict[str, dict]:
    entries = json.loads((data / "annotations" / "pairs.json").read_text(encoding="utf-8"))
    return {pair["pair_id"]: pair for entry in entries for pair in entry["pairs"]}


def load_game(game: str, games: Path, data: Path) -> list[dict]:
    """The answer key for `game`, joined with its pair polygons.

    Raises:
        HTTPException 404: no answer key for this game.
        HTTPException 500: the key names a missing, non-test, or unannotated image.
    """
    path = games / f"{game}.json"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown game {game!r}")
    key = json.loads(path.read_text(encoding="utf-8"))
    manifest = _manifest(data)
    pairs = _pairs(data)

    entries = []
    for item in key:
        image_id, pair_id = item["image_id"], item["pair_id"]
        row = manifest.get(image_id)
        problem = None
        if row is None:
            problem = "is not in manifest.csv"
        elif row["split"] != "test":
            problem = f"is in the {row['split']!r} split; games use test images only"
        elif pair_id not in pairs or not pair_id.startswith(f"{image_id}_"):
            problem = f"has no pair {pair_id!r} in pairs.json"
        elif item["correct"] not in ("a", "b"):
            problem = "has a correct answer other than 'a' or 'b'"
        if problem:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, f"{game}: image {image_id!r} {problem}"
            )
        pair = pairs[pair_id]
        entries.append({**item, "category": row["category"], "a": pair["a"], "b": pair["b"]})
    return entries


@router.get("/games/{game}/trials")
def get_trials(
    game: GameName,
    participant_id: ParticipantId,
    games: Annotated[Path, Depends(games_dir)],
    data: Annotated[Path, Depends(data_dir)],
    conditions: Annotated[list[MethodName], Depends(game_conditions)],
) -> list[GameTrial]:
    """Counterbalanced trial list for one participant. Same participant -> same list."""
    entries = load_game(game, games, data)
    number = int(participant_id[1:])
    trials = [
        GameTrial(
            trial_id=k,
            image_id=e["image_id"],
            pair_id=e["pair_id"],
            prompt=e["prompt"],
            options=["a", "b"],
            correct_answer=e["correct"],
            condition=conditions[(k + number) % len(conditions)],
            polygons={"a": e["a"], "b": e["b"]},
        )
        for k, e in enumerate(entries)
    ]
    random.Random(SEED + number).shuffle(trials)
    return trials


@router.get(
    "/games/images/{image_id}.png",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_game_image(
    image_id: ImageId,
    games: Annotated[Path, Depends(games_dir)],
    data: Annotated[Path, Depends(data_dir)],
) -> FileResponse:
    """The original dataset image (sRGB PNG). Only images used by a game are served.

    Raises:
        HTTPException 404: the image is not part of any game.
        HTTPException 503: the image is not on this machine (copy data/images/ from the Drive).
    """
    used = {
        item["image_id"]
        for path in sorted(games.glob("*.json"))
        for item in json.loads(path.read_text(encoding="utf-8"))
    }
    if image_id not in used:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"image {image_id!r} is not in a game")
    row = _manifest(data).get(image_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"image {image_id!r} not in manifest")
    # Built from the manifest category and the validated id, never from raw user input.
    path = data / "images" / row["category"] / f"{image_id}.png"
    if not path.is_file():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{image_id}.png not found; copy data/images/ from the team Drive",
        )
    return FileResponse(path, media_type="image/png")
