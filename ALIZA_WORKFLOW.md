# Aliza — ChromaFix dataset and evaluation workflow

This code is ready for data; it **does not contain the 200 source images, 50 hand-annotated pairs, or final experimental results**.

## Files implemented

- `chromafix/eval/metrics.py`: CIEDE2000 metrics with the CLAUDE.md signatures.
- `chromafix/eval/annotations.py`: load/validate/save `pairs.json`, polygon-to-mask conversion.
- `chromafix/eval/dataset.py`: manifest reader and `load_split()` for tune/test.
- `scripts/annotate_pairs.py`: click-to-annotate tool, validator, overlay previews.
- `scripts/prepare_dataset.py`: standardized PNG creation, Google Sheets CSV import, seeded stratified 30-image tune split and test split.
- `scripts/run_eval.py`: CVD types × severities × available methods, with real region pairs; writes `results/recolor_metrics.csv`.
- `scripts/analyze_study.py`: reads Iris's JSONL trial logs and outputs per-participant summaries and paired Wilcoxon comparisons.
- `tests/test_dataset_eval.py`: unit tests for the new workflow.

## 1. After the team uploads all 200 images

Download the shared Drive image folders into a local folder, e.g. `~/Downloads/ChromaFix Dataset`.
Export the source-tracker Google Sheet using **File → Download → Comma Separated Values (.csv)**.

From the project root, in your `chromafix` environment:

```bash
python -m scripts.prepare_dataset \
  --tracker ~/Downloads/ChromaFix\ Image\ Source\ Tracker.csv \
  --source-root ~/Downloads/ChromaFix\ Dataset \
  --tune-count 30
```

The script expects images directly inside the root or a category subfolder. It converts JPG/WebP/SVG to PNG (SVG needs `pip install cairosvg`), resizes longest side to at most 1024 pixels, and writes `data/images/<category>/<image_id>.png` and `data/manifest.csv`.

**Important:** Exported Sheet columns are `Filename, Category, Collected By, Source Type, Source URL`. License remains blank in the CSV manifest unless separately documented. The existing manifest header is preserved for compatibility with teammates' scripts. `lighting` is set to `na` pending image-specific review. `has_pairs` is `0` until `annotate_pairs check` sets it to `1`. Images are not committed to GitHub.

## 2. Annotate region pairs

`data/annotations/pairs.json` follows CLAUDE.md Section 7 (a list, one entry per image):

```json
[
  {"image_id": "charts_0012",
   "pairs": [{"pair_id": "charts_0012_p0",
              "a": [[x, y], [x, y], [x, y]],
              "b": [[x, y], [x, y], [x, y]],
              "note": "red line vs green line"}]}
]
```

`[x, y]` = (column, row) in pixels of the standardized PNG in `data/images/`. Don't hand-edit;
use the tool:

```bash
python -m scripts.annotate_pairs add charts_0012     # click a, Enter; click b, Enter; type note
python -m scripts.annotate_pairs check               # validate + set has_pairs (0/1) in manifest
python -m scripts.annotate_pairs preview             # overlays in results/annotation_previews/
```

Left-click adds a vertex, right-click removes the last one. Regions a and b must not overlap.

**Annotate all 30 `tune` images as well as ~50 `test` images** (done: see Data provenance). Anshika tunes personalized
daltonization by maximizing pair distinguishability on the tune split, so tune images without
pairs give her nothing to optimize. Run `check` before every commit; CI fails if `has_pairs`
and `pairs.json` disagree.

## 3. Metrics and evaluation

`chromafix/eval/metrics.py` (signatures from CLAUDE.md Section 6):

- `pair_distinguishability(img, pairs, cvd_type, severity)` → CIEDE2000 per pair. Simulates
  `img` itself, then compares the mean **Lab** of region a and region b. Pass the unsimulated
  (original or recolored) image.
- `naturalness(original, recolored)` → mean per-pixel CIEDE2000, normal vision.
- `pairs_below_jnd(distances)` → fraction of pairs below `constants.JND_DE00`.

`chromafix/eval/dataset.py` gives `load_split("tune")` / `load_split("test")`, which yield each
image as linear RGB plus its pairs. Tuning code must only call it with `"tune"`.

```bash
python -m scripts.run_eval                    # test split -> results/recolor_metrics.csv
python -m scripts.run_eval --annotated-only   # only images with pairs (faster)
```

Columns: `image_id,category,cvd_type,severity,method,pair_de00_mean,pairs_below_jnd,naturalness`.
Recoloring goes through `chromafix.recolor.recolor`. Methods that aren't ready
(`personalized` before tuning, `neural` without a model) are skipped with a message, never
filled in. Unannotated images get naturalness only; their pair columns are blank. About 1.5 s
per image on a laptop.

Higher `pair_de00_mean` and lower `pairs_below_jnd` = easier to tell apart after simulation.
Lower `naturalness` = closer to the original. `JND_DE00` in `chromafix/constants.py` is still a
placeholder (1.0) and needs a cited source.

## Data provenance (for the report)

**Pair annotations** (`data/annotations/pairs.json`): 200 pairs on 80 images: all 30 tune
images except `charts_0031` (its 2 px bump-chart lines are too thin for a region), plus 51 test
images chosen across all six categories for color-coded content. They were **drafted with AI
assistance (Claude) and reviewed by Aliza**. Method: scikit-image Felzenszwalb segmentation
proposed uniform-color regions, each reduced to its largest inscribed rectangle; for thin
lines, small lamps and scatter clusters, a seeded color flood-fill (or a manual box) was used.
A human-readable choice of which two regions form a pair (e.g. "red pepper vs green pepper")
was made per image, and every pair was checked automatically: regions non-overlapping and
inside the image, CIEDE2000 between the two regions >= 5 for normal vision, and overlays
inspected. Spot-check overlays with `python -m scripts.annotate_pairs preview`.

**Licenses** (`license` column + `data/license_review.csv`): 100 rows were blank. 8 now have a
verified open license or public-domain status (CDC, NWS, Penn State GEOG 160, UC Berkeley
Library, Wilke's and the tmap books). The other 92 are `unknown`: no license is stated
(blogs, vendors, forums, Reddit, eBay, Amazon, iStock), so they are all-rights-reserved by
default. 20 of them were opened and checked; the rest are noted as not individually verified.
Use these images for internal evaluation only and do not redistribute them; consider
replacing `traffic_0028` (iStock), `maps_0024` (eBay) and `maps_0029` (Amazon). Two
CC BY-NC-ND images (`charts_0040`, `maps_0015`) must not be redistributed in recolored form.

**Lighting** for the 16 team photos was labeled from the photos themselves (daylight / indoor /
low); confirm with Iris, who took them.

## Phase 3: evaluation, study analysis, report

```bash
python -m scripts.run_eval --root .         # -> results/recolor_metrics.csv (~8 min)
python -m scripts.report_assets --root .    # -> results/report/{tables,figures,numbers.tex}
python -m scripts.analyze_study            # -> results/study_*.csv, results/report/tables/study.tex
cd report && latexmk -pdf main.tex          # -> report/main.pdf
```

- `run_eval` currently covers `none` and `fixed`; `personalized` and `neural` are skipped until
  Anshika's code lands, then appear on the next run. `--shard K/N` splits the run.
- `report_assets` derives every table, figure, and quoted number; the report text uses its
  macros, so re-running updates the paper.
- `analyze_study` reduces each participant to one accuracy and one median correct-trial RT per
  condition, then runs paired two-sided Wilcoxon signed-rank tests with Holm correction and the
  rank-biserial r, for all participants and for those screened with a CVD. With no logs it writes
  an explicit "no sessions yet" table.

## 4. Study logs

```bash
python -m scripts.analyze_study
```

When Iris's `results/study/*.jsonl` files are present, this writes `results/study_participants.csv`, `results/study_conditions.csv`, `results/study_comparisons.csv`, and the report table. See Phase 3 above for the method. No fake results are produced.

## 5. Tests

```bash
python -m pytest tests/test_dataset_eval.py tests/test_metrics.py -q
pytest && ruff check . && ruff format --check .   # what CI runs
```

## Remaining tasks needing external data or teammates

1. When Anshika's personalized (and neural) recoloring lands: re-run `run_eval`, `report_assets`,
   and rebuild the report; then write the one interpretive sentence marked TODO in section 6.
2. When Iris's study sessions are done: copy `results/study/*.jsonl`, run `analyze_study`,
   rebuild, and interpret the comparisons (TODO in the user-study subsection).
3. Collect teammates' sections into `report/sec/` and write the abstract, intro, and
   conclusion together.
