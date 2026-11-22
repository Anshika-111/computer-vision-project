# Aliza — ChromaFix dataset and evaluation workflow

This code is ready for data; it **does not contain the 200 source images, 50 hand-annotated pairs, or final experimental results**.

## Files implemented

- `chromafix/eval/metrics.py`: existing tested CIEDE2000 metrics (left intact).
- `chromafix/eval/annotations.py`: polygon validation and polygon-to-mask conversion.
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

**Important:** Exported Sheet columns are `Filename, Category, Collected By, Source Type, Source URL`. License remains blank in the CSV manifest unless separately documented. The existing manifest header is preserved for compatibility with teammates' scripts. `lighting` is set to `na` pending image-specific review. `has_pairs` remains false until annotations are completed. Images are not committed to GitHub.

## 2. Annotate ~50 test images

The `data/annotations/pairs.json` schema is:

```json
{
  "images": {
    "charts_001": [
      {
        "a": [[10, 20], [35, 20], [35, 60], [10, 60]],
        "b": [[50, 20], [75, 20], [75, 60], [50, 60]]
      }
    ]
  }
}
```

**The example above is illustrative only: do not copy coordinates as real annotations.** Image IDs must match `manifest.csv`. Polygons must contain at least 3 [x,y] points each, fit within the standardized image, and not overlap. Annotate **test** images only. The existing `pairs.json` is intentionally empty until images can be inspected. After annotation, update corresponding `has_pairs` entries in `manifest.csv` to `true`.

## 3. Evaluate

```bash
python -m scripts.run_eval
```

This writes a header-only `results/recolor_metrics.csv` when no annotated test images exist. Once annotations exist, it evaluates the **none** baseline automatically. Optional methods must be connected after Anshika supplies implementations. Each adapter is a Python callable with signature `(linear_rgb_image, cvd_type, severity) -> linear_rgb_image`, where the arrays are float32 RGB in [0,1]. Supply an import path such as:

```bash
python -m scripts.run_eval --fixed chromafix.recolor:fixed_filter --personalized chromafix.recolor:personalized_filter
```

The paths above are **examples, not files currently present**. The runner intentionally does not assume unfinished teammates' function signatures.

Interpretation: higher `mean_de00` and lower `fraction_below_jnd` indicate better distinguishability *after CVD simulation*. Lower `naturalness_de00` means less visual change to the original. Per-image rows are not a substitute for aggregate plots and report discussion. The JND threshold in `chromafix/constants.py` is a placeholder and must be justified in the report.

## 4. Study logs

```bash
python -m scripts.analyze_study
```

When Iris's `results/study/*.jsonl` files are present, this generates `results/study_summary.csv` and `results/study_comparisons.csv`. Comparisons use participant-level means and are exploratory; ensure matched study conditions and trial difficulty before drawing causal conclusions. No fake results are produced.

## 5. Tests

```bash
python -m pytest tests/test_dataset_eval.py tests/test_metrics.py -q
python -m pytest tests/ -q
```

## Remaining tasks needing external data or teammates

1. Import the final images and source tracker; check source rights and confirm lighting metadata if needed.
2. Visually choose and annotate about 50 actual test images; mark `has_pairs`.
3. Integrate Anshika's fixed/personalized (and optional neural) recoloring methods.
4. Run experiments, summarize across categories/types/severities, generate report-ready plots and findings.
5. Import Iris's study logs and interpret study results.

## 6. Generate plots from observed evaluation results

After evaluation produces nonempty CSV data:

```bash
python -m scripts.plot_eval
```

Creates three PNG plots under `results/plots/`. Requires `matplotlib`. These are preliminary method-level summaries; report conclusions should also examine type, severity and category, and account for differences in annotation count per image.
