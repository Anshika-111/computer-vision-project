"""Smoke tests for POST /api/logs. Author: Iris."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.routes.logs import study_dir

# The example trial from CLAUDE.md Section 7.
TRIAL = {
    "session_id": "s_20261120_01",
    "participant_id": "P07",
    "profile": {"type": "deutan", "severity": 0.6, "confidence": 0.8},
    "game": "ripe_fruit",
    "trial_id": 12,
    "image_id": "fruit_0021",
    "condition": "personalized",
    "answer": "left",
    "correct": True,
    "rt_ms": 1840,
    "timestamp": "2026-11-20T18:04:11Z",
}


@pytest.fixture
def log_dir(tmp_path: Path):
    app.dependency_overrides[study_dir] = lambda: tmp_path
    yield tmp_path
    app.dependency_overrides.clear()


@pytest.fixture
def client(log_dir: Path) -> TestClient:
    return TestClient(app)


def test_log_is_written_unchanged(client: TestClient, log_dir: Path) -> None:
    response = client.post("/api/logs", json=TRIAL)

    assert response.status_code == 204
    assert response.content == b""
    lines = (log_dir / "s_20261120_01.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in lines] == [TRIAL]


def test_trials_append_one_line_each(client: TestClient, log_dir: Path) -> None:
    for trial_id in (1, 2, 3):
        assert client.post("/api/logs", json={**TRIAL, "trial_id": trial_id}).status_code == 204

    lines = (log_dir / "s_20261120_01.jsonl").read_text().splitlines()
    assert [json.loads(line)["trial_id"] for line in lines] == [1, 2, 3]


def test_sessions_go_to_separate_files(client: TestClient, log_dir: Path) -> None:
    client.post("/api/logs", json=TRIAL)
    client.post("/api/logs", json={**TRIAL, "session_id": "s_20261120_02"})

    assert sorted(p.name for p in log_dir.iterdir()) == [
        "s_20261120_01.jsonl",
        "s_20261120_02.jsonl",
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"session_id": "../../etc/passwd"},  # must not escape the log directory
        {"participant_id": "Iris"},  # no names in logs
        {"participant_name": "Iris"},  # unknown fields are rejected
        {"condition": "magic"},
        {"profile": {"type": "deutan", "severity": 1.5}},
        {"profile": {"type": "normal", "severity": 0.4}},
        {"rt_ms": -1},
        {"timestamp": "yesterday"},
        {"timestamp": "2026-11-20T18:04:11"},  # no timezone
    ],
)
def test_invalid_log_is_rejected_and_not_written(
    client: TestClient, log_dir: Path, bad: dict
) -> None:
    response = client.post("/api/logs", json={**TRIAL, **bad})

    assert response.status_code == 422
    assert list(log_dir.iterdir()) == []


def test_missing_field_is_rejected(client: TestClient) -> None:
    incomplete = {k: v for k, v in TRIAL.items() if k != "rt_ms"}

    assert client.post("/api/logs", json=incomplete).status_code == 422
