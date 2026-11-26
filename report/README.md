# ChromaFix final report (CVPR template)

Compiled by Aliza. Template files `cvpr.sty`, `ieeenat_fullname.bst` and `preamble.tex` are
from the official CVPR author kit (https://github.com/cvpr-org/author-kit), unchanged.

## Who writes what

| File | Owner |
|---|---|
| `sec/0_abstract.tex`, `sec/1_intro.tex`, `sec/7_conclusion.tex` | whole team |
| `sec/2_simulation_screening.tex` | Avneet |
| `sec/3_recoloring.tex` | Anshika |
| `sec/4_app.tex` | Iris |
| `sec/5_data.tex`, `sec/6_evaluation.tex`, `main.tex`, `refs.bib` | Aliza |

Replace the red `\TODO{...}` block in your file with your section. Add references to
`refs.bib`. Put figures in `figures/` (create it) or `../results/report/figures/`.

## Numbers are generated, never typed

Every number in the data and evaluation sections is a macro (`\ResPairFixedDeutan`,
`\NumTest`, ...) from `results/report/numbers.tex` and `results/report/study_numbers.tex`.
Tables come from `results/report/tables/`. To refresh after new results:

```bash
python -m scripts.run_eval --root .            # all test images x types x severities
python -m scripts.report_assets --root .       # tables, figures, numbers.tex
python -m scripts.analyze_study               # study tables + study_numbers.tex
cd report && latexmk -pdf main.tex
```

`run_eval` takes about 8 minutes on a laptop; add `--shard K/N` to split it across terminals
and concatenate the CSVs. Personalized/neural paragraphs and the study results switch on
automatically once their data exists.
