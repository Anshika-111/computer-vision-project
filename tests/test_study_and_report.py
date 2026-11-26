"""Tests for the study analysis and report-asset scripts. Author: Aliza.

All logs and metrics here are synthetic fixtures for testing the code, not study results.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze_study import analyze, holm, load_trials, rank_biserial
from scripts.report_assets import build
from scripts.run_eval import FIELDS


def trial(pid, cond, k, correct, rt, cvd="deutan", session=None):
    return {
        "session_id": session or f"s_{pid}",
        "participant_id": pid,
        "profile": {"type": cvd, "severity": 0.6 if cvd != "normal" else 0.0, "confidence": 1},
        "game": "color_match",
        "trial_id": k,
        "image_id": "charts_0002",
        "condition": cond,
        "answer": "a",
        "correct": correct,
        "rt_ms": rt,
        "timestamp": "2026-11-20T18:04:11Z",
    }


def write_logs(log_dir: Path, trials: list[dict]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    by_session = {}
    for t in trials:
        by_session.setdefault(t["session_id"], []).append(t)
    for sid, ts in by_session.items():
        (log_dir / f"{sid}.jsonl").write_text("".join(json.dumps(t) + "\n" for t in ts))


def synthetic_study(n=8):
    """Fixed is always more accurate and faster than none for these fake participants."""
    trials = []
    for i in range(n):
        pid = f"P{i + 1:02d}"
        cvd = "normal" if i < 2 else "deutan"
        for k in range(4):
            trials.append(trial(pid, "none", k, k < 2, 2000 + 100 * i, cvd))
            trials.append(trial(pid, "fixed", 10 + k, k < 4 - (i % 2), 1500 + 50 * i, cvd))
    return trials


# --- analyze_study --------------------------------------------------------------------


def test_no_logs_writes_placeholder(tmp_path):
    assert analyze(tmp_path / "logs", tmp_path / "res", tmp_path / "rep") == (0, 0)
    assert "No study sessions" in (tmp_path / "rep/tables/study.tex").read_text()
    assert "\\StudyParticipants}{0}" in (tmp_path / "rep/study_numbers.tex").read_text()


def test_paired_analysis(tmp_path):
    write_logs(tmp_path / "logs", synthetic_study())
    n_trials, n_comps = analyze(tmp_path / "logs", tmp_path / "res", tmp_path / "rep")
    assert n_trials == 64
    assert n_comps == 4  # none vs fixed x {accuracy, rt} x {all, cvd}
    with (tmp_path / "res/study_comparisons.csv").open() as f:
        comps = {(r["group"], r["metric"]): r for r in csv.DictReader(f)}
    acc = comps[("all", "accuracy")]
    assert int(acc["n_participants"]) == 8
    # none: 2/4 correct for everyone; fixed: 4/4 (even i) or 3/4 (odd i) -> mean gain 0.375
    assert float(acc["mean_difference"]) == pytest.approx(0.375)
    assert float(acc["rank_biserial"]) == 1.0  # every participant improved
    assert float(acc["wilcoxon_p"]) < 0.05
    rt = comps[("all", "median_rt_ms")]
    assert float(rt["mean_difference"]) < 0 and float(rt["rank_biserial"]) == -1.0
    assert int(comps[("cvd", "accuracy")]["n_participants"]) == 6  # P01, P02 screened normal
    with (tmp_path / "res/study_conditions.csv").open() as f:
        summ = {(r["group"], r["condition"]): r for r in csv.DictReader(f)}
    assert float(summ[("all", "none")]["accuracy_mean"]) == 0.5
    table = (tmp_path / "rep/tables/study.tex").read_text()
    assert "Fixed & 8 &" in table and "None & 8 & 50.0" in table


def test_duplicate_trials_counted_once(tmp_path):
    t = trial("P01", "none", 0, True, 1000)
    write_logs(tmp_path / "logs", [t, t])
    assert len(load_trials(tmp_path / "logs")) == 1


def test_bad_log_line_rejected(tmp_path):
    bad = trial("P01", "none", 0, True, 1000)
    del bad["rt_ms"]
    write_logs(tmp_path / "logs", [bad])
    with pytest.raises(ValueError, match="rt_ms"):
        load_trials(tmp_path / "logs")
    write_logs(tmp_path / "logs", [{**trial("P01", "none", 0, True, 1), "condition": "magic"}])
    with pytest.raises(ValueError, match="condition"):
        load_trials(tmp_path / "logs")


def test_rank_biserial_and_holm():
    assert rank_biserial(np.array([1.0, 2.0, 3.0])) == 1.0
    assert rank_biserial(np.array([-1.0, -2.0])) == -1.0
    assert rank_biserial(np.array([0.0, 0.0])) == 0.0
    assert rank_biserial(np.array([1.0, -1.0])) == 0.0
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


# --- report_assets --------------------------------------------------------------------


def write_metrics(path: Path, methods=("none", "fixed")) -> None:
    rows = []
    for i in range(6):
        image_id = f"charts_{i + 1:04d}"
        for t in ("protan", "deutan", "tritan"):
            for s in (0.25, 0.5, 0.75, 1.0):
                for m in methods:
                    gain = {"none": 0.0, "fixed": 3.0 + i}[m]
                    pair = "" if i == 5 else round(20 - 10 * s + gain, 4)
                    rows.append(dict(image_id=image_id, category="charts", cvd_type=t,
                                     severity=s, method=m, pair_de00_mean=pair,
                                     pairs_below_jnd="" if i == 5 else 0.0,
                                     naturalness=0.0 if m == "none" else 4.0))  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def test_report_assets_build(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    metrics = tmp_path / "recolor_metrics.csv"
    write_metrics(metrics)
    out = tmp_path / "report"
    macros = build(repo / "data/manifest.csv", repo / "data/annotations/pairs.json", metrics, out)
    for name in ("dataset", "recolor_by_type", "recolor_by_category", "paired_tests"):
        assert (out / "tables" / f"{name}.tex").exists()
    assert (out / "figures/distinguishability_vs_severity.pdf").exists()
    assert (out / "figures/naturalness.pdf").exists()
    # Pair ΔE00 over severities .25-1: 20 - 10*0.625 = 13.75 for none; fixed adds 3..7 (mean 5).
    assert macros["ResPairNoneDeutan"] == "13.8"
    assert macros["ResPairFixedDeutan"] == "18.8"
    assert macros["ResNatFixedTritan"] == "4.0"
    assert macros["ResImprovedFixedProtan"] == "5/5"  # image 6 has no pairs
    assert macros["NumImages"] == 200 and macros["NumTune"] == 30
    assert "Personalized" not in (out / "tables/recolor_by_type.tex").read_text()
    text = (out / "numbers.tex").read_text()
    assert "\\newcommand{\\ResPairFixedDeutan}{18.8}" in text


def test_report_assets_without_metrics_rows(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    metrics = tmp_path / "recolor_metrics.csv"
    metrics.write_text(",".join(FIELDS) + "\n")
    macros = build(repo / "data/manifest.csv", repo / "data/annotations/pairs.json", metrics,
                   tmp_path / "report")  # fmt: skip
    assert macros["NumMethodsEvaluated"] == 0
    assert not (tmp_path / "report/tables/recolor_by_type.tex").exists()
