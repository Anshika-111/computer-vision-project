"""Tests for Aliza's annotation, dataset, and study-analysis tools."""
import csv
import json
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from chromafix.eval.annotations import polygon_mask, pair_masks, load_annotations
from scripts.prepare_dataset import prepare
from scripts.analyze_study import analyze


def test_polygon_masks():
    mask = polygon_mask([[1, 1], [4, 1], [4, 4], [1, 4]], (8, 8))
    assert mask.dtype == bool and mask[2, 2] and not mask[0, 0]
    with pytest.raises(ValueError):
        polygon_mask([[1, 1], [2, 2]], (8, 8))
    with pytest.raises(ValueError):
        polygon_mask([[1, 1], [20, 2], [2, 3]], (8, 8))


def test_pair_overlap_rejected():
    with pytest.raises(ValueError, match="overlap"):
        pair_masks({"a": [[1, 1], [4, 1], [4, 4]], "b": [[2, 2], [5, 2], [5, 5]]}, (8, 8))


def test_load_annotations(tmp_path):
    p = tmp_path / "pairs.json"
    p.write_text('{"images": {"charts_001": [{"a": [[0,0],[1,0],[1,1]], "b": [[2,2],[3,2],[3,3]]}]}}')
    assert len(load_annotations(p)["charts_001"]) == 1


def test_prepare_dataset(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    for i in range(4):
        Image.new("RGB", (200, 100), (255, 0, 0)).save(source / f"charts_{i:03}.png")
    tracker = tmp_path / "tracker.csv"
    with tracker.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["Filename", "Category", "Collected By", "Source Type", "Source URL"])
        for i in range(4):
            w.writerow([f"charts_{i:03}.png", "Charts", "Aliza", "web", f"https://example.com/{i}"])
    out = tmp_path / "data" / "images"
    manifest = tmp_path / "data" / "manifest.csv"
    assert prepare(tracker, source, out, manifest, tune_count=1, max_side=64) == 4
    with manifest.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4 and sum(r["split"] == "tune" for r in rows) == 1
    assert Image.open(out / "charts" / "charts_000.png").size == (64, 32)


def test_study_no_logs(tmp_path):
    assert analyze(tmp_path / "logs", tmp_path / "summary.csv", tmp_path / "paired.csv") == (0, 0)
    assert (tmp_path / "summary.csv").exists()
