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

**Annotate all 30 `tune` images as well as ~50 `test` images.** Anshika tunes personalized
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

## 4. Study logs

```bash
python -m scripts.analyze_study
```

When Iris's `results/study/*.jsonl` files are present, this generates `results/study_summary.csv` and `results/study_comparisons.csv`. Comparisons use participant-level means and are exploratory; ensure matched study conditions and trial difficulty before drawing causal conclusions. No fake results are produced.

## 5. Tests

```bash
python -m pytest tests/test_dataset_eval.py tests/test_metrics.py -q
pytest && ruff check . && ruff format --check .   # what CI runs
```

## Remaining tasks needing external data or teammates

1. Import the final images and source tracker; check source rights and confirm lighting metadata if needed.
2. Annotate the 30 tune images and ~50 test images; run `annotate_pairs check`.
3. Set `JND_DE00` with a cited source (file is Avneet's; coordinate with him).
4. Run experiments, summarize across categories/types/severities, generate report-ready plots and findings.
5. Import Iris's study logs and interpret study results.

## 6. Generate plots from observed evaluation results

After evaluation produces nonempty CSV data:

```bash
python -m scripts.plot_eval
```

Creates three PNG plots under `results/plots/`. Requires `matplotlib`. These are preliminary method-level summaries; report conclusions should also examine type, severity and category, and account for differences in annotation count per image.
