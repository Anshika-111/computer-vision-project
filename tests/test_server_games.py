"""Tests for GET /api/games/{game}/trials and GET /api/games/images/{id}.png. Author: Iris."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server.main import app
from server.routes.games import data_dir, game_conditions, games_dir

REPO_ROOT = Path(__file__).resolve().parents[1]

SQUARE = [[0, 0], [10, 0], [10, 10]]
OTHER = [[20, 20], [30, 20], [30, 30]]

MANIFEST = """image_id,category,file,source,source_url,license,photographer,lighting,split,has_pairs
charts_0001,charts,data/images/charts/charts_0001.png,web,,CC0,,na,test,1
food_0002,food,data/images/food/food_0002.png,team,,own,Iris,indoor,test,1
maps_0003,maps,data/images/maps/maps_0003.png,web,,CC0,,na,tune,1
"""

KEY = [
    {"image_id": "charts_0001", "pair_id": "charts_0001_p0", "prompt": "Red?", "correct": "a"},
    {"image_id": "food_0002", "pair_id": "food_0002_p0", "prompt": "Green?", "correct": "b"},
]


def write_data(root: Path) -> Path:
    data = root / "data"
    (data / "annotations").mkdir(parents=True)
    (data / "manifest.csv").write_text(MANIFEST)
    pairs = [
        {"image_id": i, "pairs": [{"pair_id": f"{i}_p0", "a": SQUARE, "b": OTHER, "note": ""}]}
        for i in ("charts_0001", "food_0002", "maps_0003")
    ]
    (data / "annotations" / "pairs.json").write_text(json.dumps(pairs))
    (data / "images" / "charts").mkdir(parents=True)
    Image.new("RGB", (8, 8), (200, 10, 10)).save(data / "images" / "charts" / "charts_0001.png")
    return data


@pytest.fixture
def dirs(tmp_path: Path):
    data = write_data(tmp_path)
    games = tmp_path / "games"
    games.mkdir()
    (games / "color_match.json").write_text(json.dumps(KEY))
    app.dependency_overrides[data_dir] = lambda: data
    app.dependency_overrides[games_dir] = lambda: games
    app.dependency_overrides[game_conditions] = lambda: ["none", "fixed"]
    yield games, data
    app.dependency_overrides.clear()


@pytest.fixture
def client(dirs) -> TestClient:
    return TestClient(app)


def trials(client: TestClient, participant: str, game: str = "color_match") -> list[dict]:
    response = client.get(f"/api/games/{game}/trials", params={"participant_id": participant})
    assert response.status_code == 200, response.text
    return response.json()


# --- trials ------------------------------------------------------------------


def test_trials_shape(client: TestClient) -> None:
    body = trials(client, "P07")

    assert len(body) == len(KEY)
    by_image = {t["image_id"]: t for t in body}
    chart = by_image["charts_0001"]
    assert set(chart) == {
        "trial_id",
        "image_id",
        "pair_id",
        "prompt",
        "options",
        "correct_answer",
        "condition",
        "polygons",
    }
    assert chart["options"] == ["a", "b"]
    assert chart["correct_answer"] == "a"
    assert chart["polygons"] == {"a": SQUARE, "b": OTHER}
    assert by_image["food_0002"]["correct_answer"] == "b"


def test_trials_are_deterministic_per_participant(client: TestClient) -> None:
    assert trials(client, "P03") == trials(client, "P03")


def test_conditions_rotate_across_participants(client: TestClient) -> None:
    first = {t["image_id"]: t["condition"] for t in trials(client, "P01")}
    second = {t["image_id"]: t["condition"] for t in trials(client, "P02")}

    for image_id in first:
        assert first[image_id] != second[image_id]
    # Each participant sees every condition.
    assert set(first.values()) == {"none", "fixed"}


def test_trial_ids_are_stable_per_image(client: TestClient) -> None:
    ids_a = {t["image_id"]: t["trial_id"] for t in trials(client, "P01")}
    ids_b = {t["image_id"]: t["trial_id"] for t in trials(client, "P02")}
    assert ids_a == ids_b


def test_unknown_game_is_404(client: TestClient) -> None:
    response = client.get("/api/games/nope/trials", params={"participant_id": "P01"})
    assert response.status_code == 404


@pytest.mark.parametrize("participant", ["Alice", "P", "p01", "P12345"])
def test_bad_participant_id_is_422(client: TestClient, participant: str) -> None:
    response = client.get("/api/games/color_match/trials", params={"participant_id": participant})
    assert response.status_code == 422


def test_missing_participant_id_is_422(client: TestClient) -> None:
    assert client.get("/api/games/color_match/trials").status_code == 422


def test_tune_split_image_is_refused(client: TestClient, dirs) -> None:
    games, _ = dirs
    bad = [{"image_id": "maps_0003", "pair_id": "maps_0003_p0", "prompt": "?", "correct": "a"}]
    (games / "leaky.json").write_text(json.dumps(bad))

    response = client.get("/api/games/leaky/trials", params={"participant_id": "P01"})

    assert response.status_code == 500
    assert "test images only" in response.text


def test_unknown_pair_is_refused(client: TestClient, dirs) -> None:
    games, _ = dirs
    bad = [{"image_id": "charts_0001", "pair_id": "food_0002_p0", "prompt": "?", "correct": "a"}]
    (games / "mixed.json").write_text(json.dumps(bad))

    response = client.get("/api/games/mixed/trials", params={"participant_id": "P01"})

    assert response.status_code == 500


# --- images ------------------------------------------------------------------


def test_game_image_is_served(client: TestClient) -> None:
    response = client.get("/api/games/images/charts_0001.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_game_image_missing_locally_is_503(client: TestClient) -> None:
    assert client.get("/api/games/images/food_0002.png").status_code == 503


def test_image_not_in_a_game_is_404(client: TestClient) -> None:
    assert client.get("/api/games/images/maps_0003.png").status_code == 404


def test_image_id_pattern_blocks_paths(client: TestClient) -> None:
    assert client.get("/api/games/images/..%2Fmanifest.png").status_code in (404, 422)


# --- the real answer key -----------------------------------------------------


@pytest.mark.parametrize("game", ["color_match", "ripe_fruit"])
def test_real_answer_key_is_valid(game: str) -> None:
    """Each shipped answer key only uses annotated test-split images, balanced A/B."""
    app.dependency_overrides[game_conditions] = lambda: ["none", "fixed"]
    try:
        body = trials(TestClient(app), "P01", game)
    finally:
        app.dependency_overrides.clear()
    assert len(body) >= 8
    answers = [t["correct_answer"] for t in body]
    assert answers.count("a") == answers.count("b")
    # Both conditions appear, and no region pair is asked twice.
    assert {t["condition"] for t in body} == {"none", "fixed"}
    assert len({t["pair_id"] for t in body}) == len(body)
