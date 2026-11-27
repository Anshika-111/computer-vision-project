"""Analyze mini-game study logs: accuracy and response time per condition. Author: Aliza.

Reads every results/study/<session_id>.jsonl written by POST /api/logs (CLAUDE.md Section 7).

Method (small-sample, within-participant):
  1. Each participant's trials are reduced to one number per condition: accuracy (share
     correct) and the median response time of their *correct* trials.
  2. Conditions are compared pairwise with a two-sided Wilcoxon signed-rank test on those
     paired per-participant values; p-values are Holm-adjusted within each metric and group.
     Effect size is the matched-pairs rank-biserial correlation r (-1..1; positive = the
     second condition is higher).
  3. Everything is repeated for "screened_cvd": participants whose *screening* found a CVD,
     read from results/study/screening.csv. The profile stored in each log line is the
     profile *applied in the game*, not a diagnosis (in demos, normal-vision players get a
     simulated deutan profile), so it is never used to decide who has a CVD. Without
     screening.csv there is no screened_cvd group.

Outputs:
  results/study/screening.csv      (input, optional) participant_id,type,severity from the
                                   screening plates; no names
  results/study_participants.csv   participant x condition values
  results/study_conditions.csv     per-condition summary across participants
  results/study_comparisons.csv    paired tests
  results/report/tables/study.tex  table for the report (a placeholder row if no logs yet)
  results/report/study_numbers.tex \\newcommand macros for the report text

No log, no number: when there are no sessions the outputs say so instead of inventing data.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from chromafix.constants import ALL_TYPES, METHODS

REQUIRED = ("session_id", "participant_id", "profile", "condition", "correct", "rt_ms", "trial_id")
LABEL = {"none": "None", "fixed": "Fixed", "personalized": "Personalized", "neural": "Neural"}
GROUPS = ("all", "screened_cvd")
SCREENING_FIELDS = ("participant_id", "type", "severity")


def load_trials(log_dir: Path) -> list[dict]:
    """All trials from *.jsonl in log_dir, first copy of each (session_id, trial_id) kept.

    Raises:
        ValueError: A line is missing a required field or names an unknown condition.
    """
    trials, seen = [], set()
    for path in sorted(log_dir.glob("*.jsonl")) if log_dir.exists() else []:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            t = json.loads(line)
            missing = [k for k in REQUIRED if k not in t]
            if missing:
                raise ValueError(f"{path.name}:{n} is missing {', '.join(missing)}")
            if t["condition"] not in METHODS:
                raise ValueError(f"{path.name}:{n} has unknown condition {t['condition']!r}")
            key = (t["session_id"], t.get("game", ""), t["trial_id"])
            if key not in seen:  # a double-click or retry can post the same trial twice
                seen.add(key)
                trials.append(t)
    return trials


def load_screening(path: Path) -> dict[str, dict]:
    """participant_id -> {"type", "severity"} from the screening plates, or {} if no file.

    Raises:
        ValueError: Wrong header, an unknown CVD type, or a participant listed twice.
    """
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != SCREENING_FIELDS:
            raise ValueError(f"{path.name} header must be {','.join(SCREENING_FIELDS)}")
        out = {}
        for r in reader:
            if r["type"] not in ALL_TYPES:
                raise ValueError(
                    f"{path.name}: unknown type {r['type']!r} for {r['participant_id']}"
                )
            if r["participant_id"] in out:
                raise ValueError(f"{path.name}: {r['participant_id']} listed twice")
            out[r["participant_id"]] = {"type": r["type"], "severity": float(r["severity"] or 0)}
    return out


def participant_values(trials: list[dict], screening: dict[str, dict] | None = None) -> list[dict]:
    """One row per participant x condition: n, accuracy, median RT of correct trials.

    ``applied_type`` is the profile the game used; ``screened_type`` is the screening result
    ("" if the participant is not in screening.csv).
    """
    screening = screening or {}
    groups = defaultdict(list)
    profile = {}
    for t in trials:
        groups[(t["participant_id"], t["condition"])].append(t)
        profile.setdefault(t["participant_id"], t["profile"])
    rows = []
    for (pid, cond), ts in sorted(groups.items()):
        rts = [t["rt_ms"] for t in ts if t["correct"]]
        rows.append(
            dict(
                participant_id=pid,
                applied_type=profile[pid]["type"],
                applied_severity=profile[pid].get("severity", 0.0),
                screened_type=screening.get(pid, {}).get("type", ""),
                condition=cond,
                trials=len(ts),
                accuracy=float(np.mean([bool(t["correct"]) for t in ts])),
                median_rt_ms=float(np.median(rts)) if rts else None,
            )
        )
    return rows


def in_group(row: dict, group: str) -> bool:
    """'all', or 'screened_cvd': screening found a CVD (never the applied game profile)."""
    return group == "all" or row["screened_type"] not in ("", "normal")


def condition_summary(rows: list[dict]) -> list[dict]:
    out = []
    for group in GROUPS:
        for cond in METHODS:
            sel = [r for r in rows if r["condition"] == cond and in_group(r, group)]
            if not sel:
                continue
            acc = np.array([r["accuracy"] for r in sel])
            rts = np.array([r["median_rt_ms"] for r in sel if r["median_rt_ms"] is not None])
            out.append(
                dict(
                    group=group,
                    condition=cond,
                    participants=len(sel),
                    trials=sum(r["trials"] for r in sel),
                    accuracy_mean=float(acc.mean()),
                    accuracy_sd=float(acc.std(ddof=1)) if len(acc) > 1 else 0.0,
                    rt_median_ms=float(np.median(rts)) if rts.size else None,
                )
            )
    return out


def rank_biserial(d: np.ndarray) -> float:
    """Matched-pairs rank-biserial correlation of differences d (zeros dropped)."""
    from scipy.stats import rankdata

    d = d[d != 0]
    if d.size == 0:
        return 0.0
    ranks = rankdata(np.abs(d))
    return float((ranks[d > 0].sum() - ranks[d < 0].sum()) / ranks.sum())


def holm(p: list[float]) -> list[float]:
    p_arr = np.asarray(p, dtype=float)
    adj, running = np.empty_like(p_arr), 0.0
    for rank, i in enumerate(np.argsort(p_arr)):
        running = max(running, min(1.0, (len(p_arr) - rank) * p_arr[i]))
        adj[i] = running
    return adj.tolist()


def comparisons(rows: list[dict]) -> list[dict]:
    """Paired Wilcoxon tests for every pair of conditions, per metric and group."""
    from scipy.stats import wilcoxon

    out = []
    for group in GROUPS:
        for metric in ("accuracy", "median_rt_ms"):
            value = defaultdict(dict)
            for r in rows:
                if in_group(r, group) and r[metric] is not None:
                    value[r["condition"]][r["participant_id"]] = r[metric]
            conds = [c for c in METHODS if c in value]
            block = []
            for a, b in itertools.combinations(conds, 2):
                ids = sorted(value[a].keys() & value[b].keys())
                if len(ids) < 2:
                    continue
                d = np.array([value[b][i] - value[a][i] for i in ids])
                p = float(wilcoxon(d).pvalue) if np.any(d) else 1.0
                block.append(
                    dict(
                        group=group,
                        metric=metric,
                        baseline=a,
                        candidate=b,
                        n_participants=len(ids),
                        mean_difference=float(d.mean()),
                        rank_biserial=rank_biserial(d),
                        wilcoxon_p=p,
                    )
                )
            for row, adj in zip(block, holm([x["wilcoxon_p"] for x in block]), strict=True):
                row["p_holm"] = adj
            out += block
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def study_table(summary: list[dict], comps: list[dict]) -> str:
    lines = [
        r"\begin{tabular}{@{}lrrr@{}}",
        r"\toprule",
        r"Condition & Participants & Accuracy (\%) & Median RT (s) \\",
        r"\midrule",
    ]
    rows = [s for s in summary if s["group"] == "all"]
    if not rows:
        lines.append(r"\multicolumn{4}{c}{\emph{No study sessions logged yet.}} \\")
    for s in rows:
        rt = "--" if s["rt_median_ms"] is None else f"{s['rt_median_ms'] / 1000:.2f}"
        lines.append(
            f"{LABEL[s['condition']]} & {s['participants']} & "
            f"{100 * s['accuracy_mean']:.1f}\\,$\\pm$\\,{100 * s['accuracy_sd']:.1f} & {rt} \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def study_macros(trials: list[dict], screening: dict[str, dict], comps: list[dict]) -> dict:
    participants = {t["participant_id"] for t in trials}
    cvd = {p for p in participants if screening.get(p, {}).get("type", "normal") != "normal"}
    simulated = {
        t["participant_id"]
        for t in trials
        if t["profile"]["type"] != "normal" and t["participant_id"] not in cvd
    }
    m = {
        "StudyParticipants": len(participants),
        "StudyScreenedParticipants": len(participants & screening.keys()),
        "StudyCvdParticipants": len(cvd),
        "StudySimulatedParticipants": len(simulated),
        "StudyTrials": len(trials),
        "StudySessions": len({t["session_id"] for t in trials}),
    }
    for c in comps:
        if c["group"] != "all":
            continue
        name = (
            "Study"
            + {"accuracy": "Acc", "median_rt_ms": "Rt"}[c["metric"]]
            + LABEL[c["baseline"]]
            + LABEL[c["candidate"]]
        )
        p = c["p_holm"]  # carries its relation, so the text writes $p\StudyAcc...P$
        small = r"\ensuremath{{<}\,0.001}"
        m[name + "P"] = small if p < 0.001 else r"\ensuremath{{=}\," + f"{p:.3f}" + "}"
        m[name + "R"] = f"{c['rank_biserial']:+.2f}"
    return m


def analyze(
    log_dir: Path, results: Path, report: Path, screening_csv: Path | None = None
) -> tuple[int, int]:
    """Run the full analysis. Returns (number of trials, number of paired comparisons).

    ``screening_csv`` defaults to ``log_dir / "screening.csv"``.
    """
    trials = load_trials(log_dir)
    screening = load_screening(screening_csv or log_dir / "screening.csv")
    rows = participant_values(trials, screening)
    summary = condition_summary(rows)
    comps = comparisons(rows)
    write_csv(results / "study_participants.csv", rows,
              ["participant_id", "applied_type", "applied_severity", "screened_type",
               "condition", "trials",
               "accuracy", "median_rt_ms"])  # fmt: skip
    write_csv(results / "study_conditions.csv", summary,
              ["group", "condition", "participants", "trials", "accuracy_mean",
               "accuracy_sd", "rt_median_ms"])  # fmt: skip
    write_csv(results / "study_comparisons.csv", comps,
              ["group", "metric", "baseline", "candidate", "n_participants",
               "mean_difference", "rank_biserial", "wilcoxon_p", "p_holm"])  # fmt: skip
    (report / "tables").mkdir(parents=True, exist_ok=True)
    (report / "tables" / "study.tex").write_text(study_table(summary, comps), "utf-8")
    macros = study_macros(trials, screening, comps)
    body = "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(macros.items()))
    (report / "study_numbers.tex").write_text(
        "% Generated by scripts/analyze_study.py. Do not edit.\n" + body, "utf-8"
    )
    return len(trials), len(comps)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--logs", type=Path, default=Path("results/study"))
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--report", type=Path, default=Path("results/report"))
    args = ap.parse_args()
    n, m = analyze(args.logs, args.results, args.report)
    if n == 0:
        print(f"No study logs in {args.logs}: wrote empty tables (nothing invented).")
    else:
        print(f"Analyzed {n} trials; {m} paired comparisons.")


if __name__ == "__main__":
    main()
