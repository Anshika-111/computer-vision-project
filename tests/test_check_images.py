"""Tests for scripts/check_images.py. Author: Aliza."""

import csv
from pathlib import Path

from PIL import Image

from chromafix.eval.dataset import MANIFEST_FIELDS, read_manifest
from scripts.check_images import verify, write_checksums

REPO = Path(__file__).resolve().parents[1]


def make_repo(tmp_path: Path) -> tuple[Path, Path]:
    rows = []
    for i, size in ((1, (40, 30)), (2, (30, 40))):
        image_id = f"maps_{i:04d}"
        path = tmp_path / "data/images/maps" / f"{image_id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, (200, 30 * i, 30)).save(path)
        rows.append([image_id, "maps", f"data/images/maps/{image_id}.png", "web", "", "", "",
                     "na", "test", "0"])  # fmt: skip
    manifest = tmp_path / "data/manifest.csv"
    with manifest.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(MANIFEST_FIELDS)
        w.writerows(rows)
    checksums = tmp_path / "data/image_checksums.csv"
    assert write_checksums(manifest, tmp_path, checksums) == 2
    return manifest, checksums


def test_matching_folder_passes(tmp_path):
    _, checksums = make_repo(tmp_path)
    assert verify(checksums, tmp_path) == []


def test_raw_originals_are_caught(tmp_path):
    _, checksums = make_repo(tmp_path)
    images = tmp_path / "data/images/maps"
    Image.new("RGB", (400, 300), "red").save(images / "maps_0001.png")  # not resized
    Image.new("RGB", (30, 40), "red").save(images / "maps_0002.png", format="JPEG")  # wrong type
    problems = verify(checksums, tmp_path)
    assert len(problems) == 2
    assert problems[0].startswith("size") and "400x300" in problems[0]
    assert problems[1].startswith("not PNG")


def test_missing_extra_and_changed(tmp_path):
    _, checksums = make_repo(tmp_path)
    images = tmp_path / "data/images/maps"
    (images / "maps_0001.png").unlink()
    Image.new("RGB", (30, 40), "blue").save(images / "maps_0002.png")  # same size, new pixels
    Image.new("RGB", (5, 5)).save(images / "maps_002.png")  # a 3-digit raw name
    problems = verify(checksums, tmp_path)
    assert [p.split()[0] for p in problems] == ["missing", "content", "extra"]


def test_repo_checksums_cover_manifest():
    with (REPO / "data/image_checksums.csv").open() as f:
        listed = {r["image_id"]: r for r in csv.DictReader(f)}
    rows = read_manifest(REPO / "data/manifest.csv")
    assert set(listed) == {r["image_id"] for r in rows}
    assert all(listed[r["image_id"]]["file"] == r["file"] for r in rows)
    assert all(max(int(r["width"]), int(r["height"])) <= 1024 for r in listed.values())
