"""Tests for Aliza's dataset, annotation, evaluation, and study-analysis code."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from chromafix.eval.annotations import (
    dump_pairs,
    load_pairs,
    next_pair_id,
    pair_masks,
    parse_pairs,
    polygon_mask,
)
from chromafix.eval.dataset import MANIFEST_FIELDS, load_split, read_manifest, split_ids
from scripts.annotate_pairs import check, coverage, preview
from scripts.prepare_dataset import prepare
from scripts.run_eval import FIELDS, evaluate, write_rows

REPO = Path(__file__).resolve().parents[1]
SQUARE_A = [[1, 1], [10, 1], [10, 10], [1, 10]]
SQUARE_B = [[20, 1], [30, 1], [30, 10], [20, 10]]


def pair(pid, a=SQUARE_A, b=SQUARE_B, note=""):
    return {"pair_id": pid, "a": a, "b": b, "note": note}


# --- annotations ----------------------------------------------------------------------


def test_polygon_masks():
    mask = polygon_mask([[1, 1], [4, 1], [4, 4], [1, 4]], (8, 8))
    assert mask.dtype == bool and mask[2, 2] and not mask[0, 0]
    assert mask[1:5, 1:5].all() and mask.sum() == 16  # x = column, y = row
    with pytest.raises(ValueError):
        polygon_mask([[1, 1], [2, 2]], (8, 8))
    with pytest.raises(ValueError, match="outside"):
        polygon_mask([[1, 1], [20, 2], [2, 3]], (8, 8))


def test_polygon_x_is_column_y_is_row():
    mask = polygon_mask([[6, 0], [7, 0], [7, 1], [6, 1]], (4, 10))  # wide image, top-right
    rows, cols = np.nonzero(mask)
    assert rows.max() <= 1 and cols.min() >= 6


def test_pair_overlap_rejected():
    with pytest.raises(ValueError, match="overlap"):
        pair_masks({"a": [[1, 1], [4, 1], [4, 4]], "b": [[2, 2], [5, 2], [5, 5]]}, (8, 8))


def test_parse_contract_format_round_trip(tmp_path):
    entries = [{"image_id": "charts_0012", "pairs": [pair("charts_0012_p0", note="red vs green")]}]
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(entries))
    loaded = load_pairs(path)
    assert loaded["charts_0012"][0]["note"] == "red vs green"
    assert json.loads(dump_pairs(loaded)) == entries


@pytest.mark.parametrize(
    "raw",
    [
        {"images": {}},  # old dict format
        [{"image_id": "charts_0012"}],
        [{"image_id": "Charts-12", "pairs": []}],
        [{"image_id": "charts_0012", "pairs": [pair("charts_0013_p0")]}],
        [{"image_id": "charts_0012", "pairs": [pair("charts_0012_p0"), pair("charts_0012_p0")]}],
        [{"image_id": "charts_0012", "pairs": [pair("charts_0012_p0", a=[[1, 1], [2, 2]])]}],
        [{"image_id": "charts_0012", "pairs": []}, {"image_id": "charts_0012", "pairs": []}],
    ],
)
def test_parse_rejects_malformed(raw):
    with pytest.raises(ValueError):
        parse_pairs(raw)


def test_next_pair_id():
    assert next_pair_id("maps_0001", []) == "maps_0001_p0"
    existing = [pair("maps_0001_p0"), pair("maps_0001_p2")]
    assert next_pair_id("maps_0001", existing) == "maps_0001_p1"


def test_repo_pairs_file_is_valid():
    load_pairs(REPO / "data/annotations/pairs.json")


# --- manifest and splits --------------------------------------------------------------


def test_repo_manifest_contract():
    rows = read_manifest(REPO / "data/manifest.csv")
    assert len(rows) == 200
    assert len({r["image_id"] for r in rows}) == 200
    tune = split_ids(rows, "tune")
    assert len(tune) == 30
    assert {r["category"] for r in rows if r["split"] == "tune"} == {r["category"] for r in rows}
    assert {r["has_pairs"] for r in rows} <= {"0", "1"}
    for r in rows:
        assert r["file"] == f"data/images/{r['category']}/{r['image_id']}.png"


def test_repo_has_pairs_matches_pairs_file():
    rows = read_manifest(REPO / "data/manifest.csv")
    annotated = set(load_pairs(REPO / "data/annotations/pairs.json"))
    assert {r["image_id"] for r in rows if r["has_pairs"] == "1"} == annotated


def make_dataset(tmp_path: Path, annotate: dict[str, list[dict]]) -> tuple[Path, Path]:
    """Two test images and one tune image, 40x32, red left / green right."""
    rows = []
    for image_id, split in (
        ("charts_0001", "test"),
        ("charts_0002", "test"),
        ("maps_0001", "tune"),
    ):
        category = image_id.split("_")[0]
        dest = tmp_path / "data/images" / category / f"{image_id}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        px = np.zeros((32, 40, 3), dtype=np.uint8)
        px[:, :16] = (200, 40, 30)
        px[:, 16:] = (60, 160, 40)
        Image.fromarray(px).save(dest)
        has = "1" if image_id in annotate else "0"
        rows.append([image_id, category, f"data/images/{category}/{image_id}.png", "web",
                     "https://example.com", "CC0", "", "na", split, has])  # fmt: skip
    manifest = tmp_path / "data/manifest.csv"
    with manifest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(MANIFEST_FIELDS)
        w.writerows(rows)
    pairs = tmp_path / "data/pairs.json"
    pairs.write_text(dump_pairs(annotate))
    return manifest, pairs


def test_load_split_only_returns_that_split(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {"maps_0001": [pair("maps_0001_p0")]})
    tune = list(load_split("tune", manifest, pairs, tmp_path))
    assert [x.image_id for x in tune] == ["maps_0001"] and len(tune[0].pairs) == 1
    assert tune[0].img.dtype == np.float32 and tune[0].img.shape == (32, 40, 3)
    test = list(load_split("test", manifest, pairs, tmp_path))
    assert [x.image_id for x in test] == ["charts_0001", "charts_0002"]
    assert list(load_split("test", manifest, pairs, tmp_path, annotated_only=True)) == []
    with pytest.raises(ValueError):
        list(load_split("train", manifest, pairs, tmp_path))


def test_load_split_missing_image(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {})
    (tmp_path / "data/images/maps/maps_0001.png").unlink()
    with pytest.raises(FileNotFoundError, match="Drive"):
        list(load_split("tune", manifest, pairs, tmp_path))


def test_read_manifest_rejects_wrong_header(tmp_path):
    bad = tmp_path / "m.csv"
    bad.write_text("image_id,category\nx,y\n")
    with pytest.raises(ValueError, match="header"):
        read_manifest(bad)


# --- annotate_pairs script ------------------------------------------------------------


def test_check_syncs_has_pairs(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {"charts_0002": [pair("charts_0002_p0")]})
    assert check(manifest, pairs, tmp_path) == []
    flags = {r["image_id"]: r["has_pairs"] for r in read_manifest(manifest)}
    assert flags == {"charts_0001": "0", "charts_0002": "1", "maps_0001": "0"}
    assert coverage(manifest, pairs) == {"test images": 1, "test pairs": 1}


def test_check_reports_problems_without_writing(tmp_path):
    big = [[1, 1], [100, 1], [100, 10]]  # wider than the 40 px image
    manifest, pairs = make_dataset(tmp_path, {"charts_0002": [pair("charts_0002_p0", a=big)]})
    before = manifest.read_text()
    problems = check(manifest, pairs, tmp_path)
    assert len(problems) == 1 and "outside" in problems[0]
    assert manifest.read_text() == before
    pairs.write_text(dump_pairs({"natural_0009": [pair("natural_0009_p0")]}))
    assert check(manifest, pairs, tmp_path) == ["natural_0009: not in manifest"]


def test_preview_writes_overlay(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {"charts_0001": [pair("charts_0001_p0")]})
    row = {r["image_id"]: r for r in read_manifest(manifest)}["charts_0001"]
    out = preview("charts_0001", row, load_pairs(pairs)["charts_0001"], tmp_path, tmp_path / "p")
    assert Image.open(out).size == (40, 32)


# --- run_eval -------------------------------------------------------------------------


def test_run_eval_grid_and_skips(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {"charts_0001": [pair("charts_0001_p0")]})
    messages = []
    rows = evaluate(manifest, pairs, tmp_path, severities=(0.5, 1.0), log=messages.append)
    # personalized (not tuned yet) and neural (no model) are skipped, not invented.
    assert {r["method"] for r in rows} == {"none", "fixed"}
    assert any("personalized" in m for m in messages) and any("neural" in m for m in messages)
    assert len(rows) == 2 * 3 * 2 * 2  # images x types x severities x methods
    assert all(r["image_id"] != "maps_0001" for r in rows)  # tune split is never evaluated
    for r in rows:
        assert list(r) == FIELDS
        if r["method"] == "none":
            assert r["naturalness"] == 0.0
        if r["image_id"] == "charts_0002":
            assert r["pair_de00_mean"] == "" and r["pairs_below_jnd"] == ""
    deutan = {
        r["method"]: r["pair_de00_mean"]
        for r in rows
        if r["image_id"] == "charts_0001" and r["cvd_type"] == "deutan" and r["severity"] == 1.0
    }
    assert deutan["fixed"] > deutan["none"]  # daltonization helps the red/green pair
    out = tmp_path / "results/recolor_metrics.csv"
    write_rows(rows, out)
    assert out.read_text().splitlines()[0] == ",".join(FIELDS)


# --- prepare_dataset and analyze_study ------------------------------------------------


def test_prepare_dataset(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for i in range(4):
        Image.new("RGB", (200, 100), (255, 0, 0)).save(source / f"charts_{i:03}.png")
    tracker = tmp_path / "tracker.csv"
    with tracker.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Filename", "Category", "Collected By", "Source Type", "Source URL"])
        for i in range(4):
            w.writerow([f"charts_{i:03}.png", "Charts", "Aliza", "web", f"https://example.com/{i}"])
    out = tmp_path / "data" / "images"
    manifest = tmp_path / "data" / "manifest.csv"
    assert prepare(tracker, source, out, manifest, tune_count=1, max_side=64) == 4
    rows = read_manifest(manifest)
    assert len(rows) == 4 and sum(r["split"] == "tune" for r in rows) == 1
    assert {r["has_pairs"] for r in rows} == {"0"}
    assert Image.open(out / "charts" / "charts_0000.png").size == (64, 32)
    assert rows[0]["image_id"] == "charts_0000"
    assert rows[0]["file"].endswith("charts_0000.png")


def test_run_eval_shards_cover_test_split_once(tmp_path):
    manifest, pairs = make_dataset(tmp_path, {})
    seen = []
    for k in range(2):
        rows = evaluate(manifest, pairs, tmp_path, methods=["none"], cvd_types=["deutan"],
                        severities=[1.0], log=lambda m: None, shard=(k, 2))  # fmt: skip
        seen += [r["image_id"] for r in rows]
    assert sorted(seen) == ["charts_0001", "charts_0002"]
    with pytest.raises(ValueError):
        evaluate(manifest, pairs, tmp_path, shard=(2, 2))
