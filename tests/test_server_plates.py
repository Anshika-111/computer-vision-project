"""Tests for the plate endpoints and POST /api/screening/score. Author: Iris."""

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from chromafix.constants import CVD_TYPES
from chromafix.profile import CVDProfile
from chromafix.screening import Plate
from server.main import app
from server.routes.plates import plates_dir
from server.routes.screening import score_function


def make_plates() -> list[Plate]:
    """A tiny validated-looking plate set: 2 controls + every type at 2 difficulties."""
    plates = [
        Plate(
            f"control_{i}",
            "normal",
            0,
            3,
            True,
            (0.2, 0.2, 0.2),
            (0.6, 0.6, 0.6),
            {t: None for t in CVD_TYPES},
        )
        for i in range(2)
    ]
    for t in CVD_TYPES:
        for d in (1, 2):
            fail = {u: (0.5 if u == t else None) for u in CVD_TYPES}
            plates.append(
                Plate(f"{t}_d{d}_0000", t, d, 7, False, (0.6, 0.4, 0.2), (0.4, 0.5, 0.2), fail)
            )
    return plates


@pytest.fixture
def plate_dir(tmp_path: Path):
    plates = make_plates()
    (tmp_path / "plates.json").write_text(json.dumps([p.to_dict() for p in plates]))
    for p in plates:
        Image.new("RGB", (8, 8), (10, 20, 30)).save(tmp_path / f"{p.plate_id}.png")
    app.dependency_overrides[plates_dir] = lambda: tmp_path
    yield tmp_path
    app.dependency_overrides.clear()


@pytest.fixture
def client(plate_dir: Path) -> TestClient:
    return TestClient(app)


# --- GET /api/plates ---------------------------------------------------------


def test_plates_hide_answers(client: TestClient) -> None:
    response = client.get("/api/plates", params={"n": 5})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 5
    for plate in body:
        assert set(plate) == {"plate_id", "target_type", "difficulty", "is_control"}


def test_plates_default_returns_all_when_fewer_than_n(client: TestClient) -> None:
    body = client.get("/api/plates").json()

    assert len(body) == len(make_plates())
    assert len({p["plate_id"] for p in body}) == len(body)


def test_plates_are_deterministic(client: TestClient) -> None:
    assert client.get("/api/plates?n=6").json() == client.get("/api/plates?n=6").json()


@pytest.mark.parametrize("n", [0, -1, 201, "x"])
def test_plates_bad_n_is_422(client: TestClient, n: object) -> None:
    assert client.get("/api/plates", params={"n": n}).status_code == 422


def test_plates_missing_is_503(tmp_path: Path) -> None:
    app.dependency_overrides[plates_dir] = lambda: tmp_path / "nowhere"
    try:
        response = TestClient(app).get("/api/plates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "make_plates.py" in response.json()["detail"]


# --- GET /api/plates/{plate_id}.png ------------------------------------------


def test_plate_image_is_png(client: TestClient) -> None:
    response = client.get("/api/plates/deutan_d1_0000.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(response.content)) as im:
        assert im.size == (8, 8)


@pytest.mark.parametrize("plate_id", ["deutan_d9_9999", "plates", "..%2Fplates"])
def test_unknown_plate_is_404_or_422(client: TestClient, plate_id: str) -> None:
    assert client.get(f"/api/plates/{plate_id}.png").status_code in (404, 422)


def test_listed_plate_without_png_is_404(client: TestClient, plate_dir: Path) -> None:
    (plate_dir / "tritan_d2_0000.png").unlink()

    assert client.get("/api/plates/tritan_d2_0000.png").status_code == 404


# --- POST /api/screening/score -----------------------------------------------


@pytest.fixture
def fake_score():
    """Stub for Avneet's scoring.score (CLAUDE.md Section 6) that records its inputs."""
    calls: list[tuple[list[dict], dict[str, Plate]]] = []

    def score(answers: list[dict], plates: dict[str, Plate]) -> CVDProfile:
        calls.append((answers, plates))
        return CVDProfile(type="deutan", severity=1.0, confidence=0.9)

    app.dependency_overrides[score_function] = lambda: score
    yield calls
    app.dependency_overrides.pop(score_function, None)


def test_score_returns_profile_json(client: TestClient, fake_score: list) -> None:
    answers = [
        {"plate_id": "deutan_d1_0000", "answer": "none"},
        {"plate_id": "control_0", "answer": "3"},
    ]

    response = client.post("/api/screening/score", json={"answers": answers})

    assert response.status_code == 200, response.text
    assert response.json() == {"type": "deutan", "severity": 1.0, "confidence": 0.9}
    ((seen_answers, seen_plates),) = fake_score
    assert seen_answers == answers
    assert set(seen_plates) == {"deutan_d1_0000", "control_0"}
    assert seen_plates["deutan_d1_0000"].fail_severity["deutan"] == 0.5


@pytest.mark.parametrize(
    "body",
    [
        {"answers": []},
        {"answers": [{"plate_id": "control_0", "answer": "12"}]},
        {"answers": [{"plate_id": "control_0", "answer": "seven"}]},
        {"answers": [{"plate_id": "control_0"}]},
        {"answers": [{"plate_id": "not_a_plate", "answer": "3"}]},
        {},
    ],
)
def test_score_bad_body_is_422(client: TestClient, fake_score: list, body: dict) -> None:
    assert client.post("/api/screening/score", json=body).status_code == 422
    assert fake_score == []


def test_score_without_scoring_module_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    real_import = builtins.__import__

    def no_scoring(name: str, *args: object, **kwargs: object):
        if name == "chromafix.screening.scoring":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_scoring)

    response = client.post(
        "/api/screening/score", json={"answers": [{"plate_id": "control_0", "answer": "3"}]}
    )

    assert response.status_code == 503
