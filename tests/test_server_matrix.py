"""Tests for GET /api/matrix and GET /api/methods. Author: Iris."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from chromafix.constants import CVD_TYPES, METHODS
from chromafix.profile import CVDProfile
from chromafix.recolor import recolor_matrix
from chromafix.simulate import simulation_matrix
from server.main import app
from server.routes import matrix as matrix_route
from server.routes import methods as methods_route


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def get_matrix(client: TestClient, **params: object) -> np.ndarray:
    response = client.get("/api/matrix", params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert list(body) == ["matrix"]
    return np.array(body["matrix"], dtype=np.float64)


# --- mode=simulate ----------------------------------------------------------


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
@pytest.mark.parametrize("severity", [0.1, 0.6, 0.65, 1.0])  # 0.65 is between grid steps
def test_simulate_matches_chromafix_exactly(
    client: TestClient, cvd_type: str, severity: float
) -> None:
    m = get_matrix(client, mode="simulate", type=cvd_type, severity=severity)

    # JSON floats round-trip exactly, so the client gets the very same numbers.
    np.testing.assert_array_equal(m, simulation_matrix(cvd_type, severity))


def test_matrix_is_row_major(client: TestClient) -> None:
    expected = simulation_matrix("protan", 1.0)
    assert expected[0, 1] != expected[1, 0]  # not symmetric, so a transpose would show

    m = get_matrix(client, mode="simulate", type="protan", severity=1.0)

    assert m[0, 1] == expected[0, 1]  # row 0 = how output red is made from (r, g, b)


@pytest.mark.parametrize(
    "params",
    [
        {"type": "normal", "severity": 0.0},
        {"type": "deutan", "severity": 0.0},
    ],
)
def test_simulate_without_cvd_is_identity(client: TestClient, params: dict) -> None:
    np.testing.assert_array_equal(get_matrix(client, mode="simulate", **params), np.eye(3))


# --- mode=recolor -----------------------------------------------------------


@pytest.mark.parametrize("cvd_type", CVD_TYPES)
def test_fixed_recolor_matches_chromafix_exactly(client: TestClient, cvd_type: str) -> None:
    m = get_matrix(client, mode="recolor", method="fixed", type=cvd_type, severity=0.6)

    expected = recolor_matrix(CVDProfile(type=cvd_type, severity=0.6), "fixed")
    np.testing.assert_array_equal(m, expected)


@pytest.mark.parametrize(
    "params",
    [
        {"method": "none", "type": "deutan", "severity": 0.6},
        {"method": "fixed", "type": "normal", "severity": 0.0},
    ],
)
def test_recolor_identity_cases(client: TestClient, params: dict) -> None:
    np.testing.assert_array_equal(get_matrix(client, mode="recolor", **params), np.eye(3))


def test_personalized_not_ready_is_503(client: TestClient, monkeypatch) -> None:
    def not_tuned(profile: CVDProfile, method: str) -> np.ndarray:
        raise NotImplementedError("not tuned yet")

    monkeypatch.setattr(matrix_route, "recolor_matrix", not_tuned)

    response = client.get(
        "/api/matrix",
        params={"mode": "recolor", "method": "personalized", "type": "deutan", "severity": 0.6},
    )

    assert response.status_code == 503
    assert "not tuned yet" in response.json()["detail"]


def test_personalized_passes_profile_through(client: TestClient, monkeypatch) -> None:
    seen: list[tuple[CVDProfile, str]] = []
    tuned = np.arange(9, dtype=np.float64).reshape(3, 3) / 10

    def fake_recolor_matrix(profile: CVDProfile, method: str) -> np.ndarray:
        seen.append((profile, method))
        return tuned

    monkeypatch.setattr(matrix_route, "recolor_matrix", fake_recolor_matrix)

    m = get_matrix(client, mode="recolor", method="personalized", type="tritan", severity=0.3)

    np.testing.assert_array_equal(m, tuned)
    assert seen == [(CVDProfile(type="tritan", severity=0.3), "personalized")]


# --- invalid requests -------------------------------------------------------

VALID = {"mode": "simulate", "type": "deutan", "severity": 0.6}


@pytest.mark.parametrize(
    "params",
    [
        {k: v for k, v in VALID.items() if k != "mode"},
        {k: v for k, v in VALID.items() if k != "type"},
        {k: v for k, v in VALID.items() if k != "severity"},
        {**VALID, "mode": "both"},
        {**VALID, "type": "achromat"},
        {**VALID, "severity": -0.1},
        {**VALID, "severity": 1.1},
        {**VALID, "severity": "nan"},
        {**VALID, "severity": "high"},
        {**VALID, "type": "normal", "severity": 0.5},
        {**VALID, "method": "fixed"},  # method only makes sense for recolor
        {**VALID, "severty": 0.6},  # typo in a parameter name
        {**VALID, "mode": "recolor"},  # recolor without a method
        {**VALID, "mode": "recolor", "method": "neural"},  # neural has no matrix
        {**VALID, "mode": "recolor", "method": "magic"},
    ],
)
def test_invalid_query_is_422(client: TestClient, params: dict) -> None:
    assert client.get("/api/matrix", params=params).status_code == 422


# --- /api/methods -----------------------------------------------------------


def test_methods_lists_only_what_works(client: TestClient) -> None:
    response = client.get("/api/methods")

    assert response.status_code == 200
    methods = response.json()
    assert methods[:2] == ["none", "fixed"]
    # Whatever the current state of Anshika's work, the list must agree with /api/matrix.
    personalized = client.get(
        "/api/matrix",
        params={"mode": "recolor", "method": "personalized", "type": "deutan", "severity": 0.5},
    )
    assert ("personalized" in methods) == (personalized.status_code == 200)


@pytest.mark.parametrize(
    ("personalized", "neural", "expected"),
    [
        (False, False, ["none", "fixed"]),
        (True, False, ["none", "fixed", "personalized"]),
        (False, True, ["none", "fixed", "neural"]),
        (True, True, list(METHODS)),
    ],
)
def test_methods_follow_availability(
    client: TestClient, monkeypatch, personalized: bool, neural: bool, expected: list[str]
) -> None:
    monkeypatch.setattr(methods_route, "personalized_available", lambda: personalized)
    monkeypatch.setattr(methods_route, "neural_available", lambda: neural)

    assert client.get("/api/methods").json() == expected


def test_neural_probe_reports_missing_model() -> None:
    # The neural model is not trained yet, so the probe must say unavailable, not crash.
    assert methods_route.neural_available() is False
