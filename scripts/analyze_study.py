"""Summarize Iris's anonymized JSONL study trials and paired condition comparisons.

Pairs observations by participant, game, image and trial_id, then performs a
Wilcoxon signed-rank test on per-participant condition means when possible.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np


def analyze(log_dir: Path, output: Path, comparisons: Path) -> tuple[int, int]:
    trials = []
    for file in sorted(log_dir.glob("*.jsonl")):
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if not all(k in record for k in ("participant_id", "condition", "correct", "rt_ms")):
                    raise ValueError(f"Incomplete study trial in {file}")
                trials.append(record)
    groups = defaultdict(list)
    for trial in trials:
        groups[(trial["participant_id"], trial["condition"])].append(trial)
    summary = []
    for (participant, condition), entries in sorted(groups.items()):
        summary.append(dict(participant_id=participant, condition=condition, trials=len(entries),
                            accuracy=float(np.mean([int(t["correct"]) for t in entries])),
                            mean_rt_ms=float(np.mean([t["rt_ms"] for t in entries]))))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["participant_id", "condition", "trials", "accuracy", "mean_rt_ms"])
        w.writeheader(); w.writerows(summary)
    paired = []
    by_condition = defaultdict(dict)
    for item in summary:
        by_condition[item["condition"]][item["participant_id"]] = item
    for baseline, candidate in (("none", "fixed"), ("fixed", "personalized"), ("none", "personalized"), ("fixed", "neural")):
        common = sorted(by_condition[baseline].keys() & by_condition[candidate].keys())
        for metric in ("accuracy", "mean_rt_ms"):
            p = ""
            if len(common) >= 2:
                from scipy.stats import wilcoxon
                a = np.array([by_condition[baseline][i][metric] for i in common])
                b = np.array([by_condition[candidate][i][metric] for i in common])
                if np.any(a != b):
                    p = float(wilcoxon(b - a).pvalue)
            if common:
                paired.append(dict(baseline=baseline, candidate=candidate, metric=metric,
                                   n_participants=len(common), mean_difference=float(np.mean([
                                       by_condition[candidate][i][metric] - by_condition[baseline][i][metric] for i in common])),
                                   wilcoxon_p=p))
    comparisons.parent.mkdir(parents=True, exist_ok=True)
    with comparisons.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["baseline", "candidate", "metric", "n_participants", "mean_difference", "wilcoxon_p"])
        w.writeheader(); w.writerows(paired)
    return len(trials), len(paired)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--logs", type=Path, default=Path("results/study"))
    ap.add_argument("--out", type=Path, default=Path("results/study_summary.csv"))
    ap.add_argument("--comparisons", type=Path, default=Path("results/study_comparisons.csv"))
    args = ap.parse_args()
    n, m = analyze(args.logs, args.out, args.comparisons)
    print(f"Analyzed {n} trials; {m} paired comparison rows. No results invented for missing logs.")


if __name__ == "__main__":
    main()
