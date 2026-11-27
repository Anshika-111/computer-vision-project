"""Build the report's tables, figures, and number macros from results CSVs. Author: Aliza.

Reads data/manifest.csv, data/annotations/pairs.json and results/recolor_metrics.csv and
writes, under results/report/:

  tables/dataset.tex           images, splits, and annotations per category
  tables/recolor_by_type.tex   method x CVD type: pair ΔE00, share below JND, naturalness
  tables/recolor_by_category.tex  pair ΔE00 per category at severity 1.0
  tables/paired_tests.tex      each method vs none, paired Wilcoxon over test images
  figures/distinguishability_vs_severity.pdf
  figures/naturalness.pdf
  figures/example.jpg          qualitative example (only if data/images is on this machine)
  numbers.tex                  \\newcommand macros the report text uses for every figure quoted

Everything is derived from the CSVs, so re-running after new methods land updates the paper.
Methods that have no rows yet are left out, never filled in.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from chromafix.constants import CVD_TYPES, EVAL_SEVERITIES, JND_DE00, METHODS

# Fixed color per method (dataviz reference palette, slots 1-4 in order), so a method keeps
# its color whether or not the others are present. Markers are a second, color-free cue.
METHOD_STYLE = {
    "none": ("#257de0", "o", "None"),
    "fixed": ("#f47230", "s", "Fixed"),
    "personalized": ("#00b894", "^", "Personalized"),
    "neural": ("#f2a600", "D", "Neural"),
}
TYPE_LABEL = {"protan": "Protan", "deutan": "Deutan", "tritan": "Tritan"}
CATEGORY_LABEL = {
    "charts": "Charts",
    "maps": "Maps",
    "traffic": "Traffic",
    "food": "Food",
    "coded_items": "Coded items",
    "natural": "Natural",
}
CATEGORIES = tuple(CATEGORY_LABEL)


def read_rows(path: Path) -> list[dict]:
    """Read recolor_metrics.csv, converting numeric columns; blank pair columns become None."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["severity"] = float(r["severity"])
        for key in ("pair_de00_mean", "pairs_below_jnd", "naturalness"):
            r[key] = float(r[key]) if r[key] != "" else None
    return rows


def present_methods(rows: list[dict]) -> list[str]:
    """Methods with at least one row, in METHODS order."""
    have = {r["method"] for r in rows}
    return [m for m in METHODS if m in have]


def per_image(rows: list[dict], metric: str, method: str, cvd_type: str, severities) -> dict:
    """image_id -> metric averaged over the given severities (images missing a value skipped)."""
    acc = defaultdict(list)
    for r in rows:
        if r["method"] == method and r["cvd_type"] == cvd_type and r["severity"] in severities:
            if r[metric] is not None:
                acc[r["image_id"]].append(r[metric])
    return {k: float(np.mean(v)) for k, v in acc.items()}


def mean_ci(values) -> tuple[float, float]:
    """Mean and 95% normal-approximation half-width across images."""
    v = np.asarray(list(values), dtype=float)
    if v.size == 0:
        return float("nan"), float("nan")
    half = 1.96 * v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0
    return float(v.mean()), float(half)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, in input order."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[i]))
        adj[i] = running
    return adj.tolist()


def fmt(x: float, digits: int = 1) -> str:
    return "--" if x is None or not np.isfinite(x) else f"{x:.{digits}f}"


def fmt_p(p: float) -> str:
    return r"\ensuremath{<}0.001" if p < 0.001 else f"{p:.3f}"  # safe in text and math


def p_relation(p: float) -> str:
    """'= 0.009' or '< 0.001' for running text: write $p\\ResP...$ with no sign of your own."""
    if p < 0.001:
        return r"\ensuremath{{<}\,0.001}"
    return r"\ensuremath{{=}\," + f"{p:.3f}" + "}"


def macro_name(*parts: str) -> str:
    """\\ResPairFixedDeutan-style name: letters only, as LaTeX requires."""
    return "Res" + "".join(p.replace("_", " ").title().replace(" ", "") for p in parts)


# --- dataset ------------------------------------------------------------------------------


def dataset_stats(manifest: Path, pairs: Path) -> dict:
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    entries = json.loads(pairs.read_text(encoding="utf-8"))
    n_pairs = {e["image_id"]: len(e["pairs"]) for e in entries}
    stats = {}
    for c in CATEGORIES + ("all",):
        sel = [r for r in rows if c == "all" or r["category"] == c]
        stats[c] = {
            "images": len(sel),
            "tune": sum(r["split"] == "tune" for r in sel),
            "test": sum(r["split"] == "test" for r in sel),
            "team": sum(r["source"] == "team" for r in sel),
            "ann_test": sum(r["split"] == "test" and r["image_id"] in n_pairs for r in sel),
            "pairs_test": sum(n_pairs.get(r["image_id"], 0) for r in sel if r["split"] == "test"),
            "ann_tune": sum(r["split"] == "tune" and r["image_id"] in n_pairs for r in sel),
            "pairs_tune": sum(n_pairs.get(r["image_id"], 0) for r in sel if r["split"] == "tune"),
            "open_license": sum(
                r["license"] not in ("", "unknown") and r["source"] != "team" for r in sel
            ),
        }
    return stats


def dataset_table(stats: dict) -> str:
    lines = [
        r"\begin{tabular}{@{}lrrrrr@{}}",
        r"\toprule",
        r"Category & Images & Tune & Test & Annot.\ test & Pairs (test) \\",
        r"\midrule",
    ]
    for c in CATEGORIES + ("all",):
        s = stats[c]
        name = r"\textbf{Total}" if c == "all" else CATEGORY_LABEL[c]
        if c == "all":
            lines.append(r"\midrule")
        lines.append(
            f"{name} & {s['images']} & {s['tune']} & {s['test']} & {s['ann_test']} & "
            f"{s['pairs_test']} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


# --- recoloring results ---------------------------------------------------------------------


def by_type_table(rows: list[dict], methods: list[str]) -> tuple[str, dict]:
    """Main results: averaged over EVAL_SEVERITIES, then mean ± 95% CI across images."""
    sev = set(EVAL_SEVERITIES)
    macros = {}
    lines = [
        r"\begin{tabular}{@{}llccc@{}}",
        r"\toprule",
        r"Type & Method & Pair $\Delta E_{00}\uparrow$ & ${<}$JND (\%)$\downarrow$ & "
        r"Natural.\ $\Delta E_{00}\downarrow$ \\",
        r"\midrule",
    ]
    for t in CVD_TYPES:
        for k, m in enumerate(methods):
            pair, pair_h = mean_ci(per_image(rows, "pair_de00_mean", m, t, sev).values())
            jnd, _ = mean_ci(per_image(rows, "pairs_below_jnd", m, t, sev).values())
            nat, nat_h = mean_ci(per_image(rows, "naturalness", m, t, sev).values())
            label = TYPE_LABEL[t] if k == 0 else ""
            lines.append(
                f"{label} & {METHOD_STYLE[m][2]} & {fmt(pair)}\\,$\\pm$\\,{fmt(pair_h)} & "
                f"{fmt(100 * jnd)} & {fmt(nat)}\\,$\\pm$\\,{fmt(nat_h)} \\\\"
            )
            macros[macro_name("pair", m, t)] = fmt(pair)
            macros[macro_name("jnd", m, t)] = fmt(100 * jnd)
            macros[macro_name("nat", m, t)] = fmt(nat)
            full, _ = mean_ci(per_image(rows, "pair_de00_mean", m, t, {1.0}).values())
            macros[macro_name("pair", m, t, "full")] = fmt(full)
        if t != CVD_TYPES[-1]:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", macros


def by_category_table(rows: list[dict], methods: list[str], macros: dict | None = None) -> str:
    """Pair ΔE00 at severity 1.0, averaged over the three CVD types, per category."""
    head = " & ".join(METHOD_STYLE[m][2] for m in methods)
    lines = [
        r"\begin{tabular}{@{}l" + "c" * len(methods) + r"@{}}",
        r"\toprule",
        f"Category & {head} \\\\",
        r"\midrule",
    ]
    for c in CATEGORIES:
        cells = []
        for m in methods:
            v = [
                r["pair_de00_mean"]
                for r in rows
                if r["category"] == c
                and r["method"] == m
                and r["severity"] == 1.0
                and r["pair_de00_mean"] is not None
            ]
            cells.append(fmt(float(np.mean(v))) if v else "--")
            if macros is not None and v:
                macros[macro_name("cat", m, c)] = fmt(float(np.mean(v)))
        lines.append(f"{CATEGORY_LABEL[c]} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def paired_tests(rows: list[dict], methods: list[str]) -> tuple[str, list[dict], dict]:
    """Each non-baseline method vs none, per CVD type, on per-image pair ΔE00 and naturalness.

    Uses all EVAL_SEVERITIES averaged per image, two-sided Wilcoxon signed-rank, Holm-adjusted
    across every test in the table.
    """
    from scipy.stats import wilcoxon

    sev = set(EVAL_SEVERITIES)
    tests = []
    for m in methods:
        if m == "none":
            continue
        for t in CVD_TYPES:
            base = per_image(rows, "pair_de00_mean", "none", t, sev)
            cand = per_image(rows, "pair_de00_mean", m, t, sev)
            ids = sorted(base.keys() & cand.keys())
            d = np.array([cand[i] - base[i] for i in ids])
            if len(ids) < 2 or not np.any(d):
                continue
            res = wilcoxon(d)
            tests.append(
                dict(
                    method=m,
                    cvd_type=t,
                    n=len(ids),
                    median_diff=float(np.median(d)),
                    improved=int((d > 0).sum()),
                    p=float(res.pvalue),
                )
            )
    for row, adj in zip(tests, holm([x["p"] for x in tests]), strict=True):
        row["p_holm"] = adj
    lines = [
        r"\begin{tabular}{@{}llrrrr@{}}",
        r"\toprule",
        r"Method & Type & $n$ & Median $\Delta$ & Improved & $p_\mathrm{Holm}$ \\",
        r"\midrule",
    ]
    macros = {}
    for x in tests:
        lines.append(
            f"{METHOD_STYLE[x['method']][2]} & {TYPE_LABEL[x['cvd_type']]} & {x['n']} & "
            f"{x['median_diff']:+.1f} & {x['improved']}/{x['n']} & {fmt_p(x['p_holm'])} \\\\"
        )
        key = (x["method"], x["cvd_type"])
        macros[macro_name("med", *key)] = f"{x['median_diff']:+.1f}"
        macros[macro_name("improved", *key)] = f"{x['improved']}/{x['n']}"
        macros[macro_name("p", *key)] = p_relation(x["p_holm"])
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n", tests, macros


# --- figures --------------------------------------------------------------------------------


def _mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 7,
            "axes.titlesize": 7.5,
            "axes.labelsize": 7,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#9c9c9c",
            "axes.linewidth": 0.6,
            "xtick.color": "#5c5c5c",
            "ytick.color": "#5c5c5c",
            "axes.labelcolor": "#1f1f1f",
            "text.color": "#1f1f1f",
            "axes.grid": True,
            "grid.color": "#e6e6e6",
            "grid.linewidth": 0.5,
            "pdf.fonttype": 42,
        }
    )
    return plt


def severity_figure(rows: list[dict], methods: list[str], out: Path) -> None:
    """Small multiples: mean pair ΔE00 vs severity, one panel per CVD type, one line per method."""
    plt = _mpl()
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.0), sharey=True)
    for ax, t in zip(axes, CVD_TYPES, strict=True):
        for m in methods:
            color, marker, label = METHOD_STYLE[m]
            ys = [
                mean_ci(per_image(rows, "pair_de00_mean", m, t, {s}).values())[0]
                for s in EVAL_SEVERITIES
            ]
            ax.plot(EVAL_SEVERITIES, ys, color=color, lw=2, marker=marker, ms=4.5,
                    markeredgecolor="white", markeredgewidth=0.8, label=label)  # fmt: skip
            ax.annotate(label, (EVAL_SEVERITIES[-1], ys[-1]), xytext=(4, 0),
                        textcoords="offset points", va="center", fontsize=6.5)  # fmt: skip
        ax.set_title(TYPE_LABEL[t])
        ax.set_xticks(EVAL_SEVERITIES)
        ax.set_xlim(0.2, 1.22)
        ax.set_xlabel("Severity")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel(r"Mean pair $\Delta E_{00}$ (after simulation)")
    axes[0].legend(loc="lower left", frameon=False)
    fig.tight_layout(w_pad=1.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def naturalness_figure(rows: list[dict], methods: list[str], out: Path) -> None:
    """Grouped bars: naturalness cost per method, grouped by CVD type, values printed on bars."""
    plt = _mpl()
    shown = [m for m in methods if m != "none"] or methods  # none is 0 by definition
    fig, ax = plt.subplots(figsize=(3.3, 1.9))
    width = 0.8 / len(shown)
    x = np.arange(len(CVD_TYPES))
    for k, m in enumerate(shown):
        color, _, label = METHOD_STYLE[m]
        vals = [
            mean_ci(per_image(rows, "naturalness", m, t, set(EVAL_SEVERITIES)).values())[0]
            for t in CVD_TYPES
        ]
        pos = x + (k - (len(shown) - 1) / 2) * width
        bars = ax.bar(pos, vals, width=width * 0.92, color=color, label=label, zorder=3)
        ax.bar_label(bars, labels=[f"{v:.1f}" for v in vals], padding=2, fontsize=6.5)
    ax.set_xticks(x, [TYPE_LABEL[t] for t in CVD_TYPES])
    ax.set_ylabel(r"Naturalness $\Delta E_{00}$ ($\downarrow$)")
    ax.grid(axis="x", visible=False)
    ax.margins(y=0.18)
    if len(shown) > 1:  # one series needs no legend; the axis label names it
        ax.legend(frameon=False, ncol=len(shown), loc="lower center", bbox_to_anchor=(0.5, 1.0))
    else:
        ax.set_title(f"{METHOD_STYLE[shown[0]][2]} recoloring", loc="left")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def example_figure(manifest: Path, root: Path, image_id: str, cvd_type: str, severity: float,
                   out: Path, width: int = 480) -> bool:  # fmt: skip
    """Original / simulated / fixed-recolored / simulated recolored, in one row.

    Returns False (and writes nothing) if the image is not on this machine.
    """
    from PIL import Image

    from chromafix.color import linear_to_srgb, load_image, to_uint8
    from chromafix.profile import CVDProfile
    from chromafix.recolor import recolor
    from chromafix.simulate import simulate

    with manifest.open(newline="", encoding="utf-8") as f:
        row = {r["image_id"]: r for r in csv.DictReader(f)}[image_id]
    path = root / row["file"]
    if not path.exists():
        return False
    img = load_image(path)
    fixed = recolor(img, CVDProfile(type=cvd_type, severity=severity), "fixed")
    panels = [img, simulate(img, cvd_type, severity), fixed, simulate(fixed, cvd_type, severity)]
    tiles = []
    for p in panels:
        t = Image.fromarray(to_uint8(linear_to_srgb(p)))
        t.thumbnail((width, width))
        tiles.append(t)
    gap = 8
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + gap * 3, tiles[0].height), "white")
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + gap
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=90)
    return True


# --- driver ---------------------------------------------------------------------------------


def write_macros(macros: dict, path: Path) -> None:
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items()))
    path.write_text("% Generated by scripts/report_assets.py. Do not edit.\n" + body, "utf-8")


EXAMPLE = ("natural_0001", "deutan", 1.0)  # a team photo, so there is no license question


def build(manifest: Path, pairs: Path, metrics: Path, out: Path, root: Path | None = None) -> dict:
    """Write every table, figure, and macro file. Returns the macro dict."""
    tables, figures = out / "tables", out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    stats = dataset_stats(manifest, pairs)
    (tables / "dataset.tex").write_text(dataset_table(stats), "utf-8")
    s = stats["all"]
    macros = {
        "NumImages": s["images"],
        "NumTune": s["tune"],
        "NumTest": s["test"],
        "NumTeamPhotos": s["team"],
        "NumWebImages": s["images"] - s["team"],
        "NumAnnotTest": s["ann_test"],
        "NumPairsTest": s["pairs_test"],
        "NumAnnotTune": s["ann_tune"],
        "NumPairsTune": s["pairs_tune"],
        "NumOpenLicense": s["open_license"],
        "NumNoLicense": s["images"] - s["team"] - s["open_license"],
        "JndValue": fmt(JND_DE00),
    }

    rows = read_rows(metrics)
    methods = present_methods(rows)
    macros["NumMethodsEvaluated"] = len(methods)
    macros["NumEvalRows"] = len(rows)
    if rows:
        tex, m = by_type_table(rows, methods)
        (tables / "recolor_by_type.tex").write_text(tex, "utf-8")
        macros.update(m)
        cat_tex = by_category_table(rows, methods, macros)
        (tables / "recolor_by_category.tex").write_text(cat_tex, "utf-8")
        tex, _, m = paired_tests(rows, methods)
        (tables / "paired_tests.tex").write_text(tex, "utf-8")
        macros.update(m)
        severity_figure(rows, methods, figures / "distinguishability_vs_severity.pdf")
        naturalness_figure(rows, methods, figures / "naturalness.pdf")
        if root is not None:
            image_id, t, sev = EXAMPLE
            if example_figure(manifest, root, image_id, t, sev, figures / "example.jpg"):
                macros["ExampleImage"] = image_id.replace("_", r"\_")
    write_macros(macros, out / "numbers.tex")
    return macros


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    ap.add_argument("--pairs", type=Path, default=Path("data/annotations/pairs.json"))
    ap.add_argument("--metrics", type=Path, default=Path("results/recolor_metrics.csv"))
    ap.add_argument("--out", type=Path, default=Path("results/report"))
    ap.add_argument("--root", type=Path, default=Path("."), help="repo root holding data/images")
    args = ap.parse_args()
    macros = build(args.manifest, args.pairs, args.metrics, args.out, args.root)
    print(f"Wrote tables, figures and {len(macros)} macros to {args.out}")


if __name__ == "__main__":
    main()
