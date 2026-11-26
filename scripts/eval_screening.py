"""Simulated-observer evaluation of the screening test. Author: Avneet.

Every type × severity takes the test as a simulated viewer, optionally with random lapses,
and the script reports type accuracy and severity mean absolute error.
Writes results/screening_eval.csv (one row per trial) and prints a summary.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from chromafix.constants import ALL_TYPES, CVD_TYPES, SEED
from chromafix.profile import CVDProfile
from chromafix.screening import Plate, score, select_plates, simulated_answers


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plates", type=Path, default=Path("data/plates/plates.json"))
    ap.add_argument("--n", type=int, default=24, help="plates per test (0 = all plates)")
    ap.add_argument("--lapse-rates", nargs="+", type=float, default=[0.0, 0.05, 0.1])
    ap.add_argument("--repeats", type=int, default=20, help="test sessions per observer")
    ap.add_argument("--out", type=Path, default=Path("results/screening_eval.csv"))
    args = ap.parse_args()

    plates = [Plate.from_dict(d) for d in json.loads(args.plates.read_text())]
    by_id = {p.plate_id: p for p in plates}
    rng = np.random.default_rng(SEED)
    observers = [CVDProfile.normal()] + [
        CVDProfile(t, round(s, 1)) for t in CVD_TYPES for s in np.arange(0.1, 1.01, 0.1)
    ]
    rows = []
    for lapse in args.lapse_rates:
        for obs in observers:
            for rep in range(args.repeats if lapse > 0 else 1):
                shown = plates if args.n == 0 else select_plates(plates, args.n, seed=rep)
                answers = simulated_answers(shown, obs, lapse_rate=lapse, rng=rng)
                est = score(answers, by_id)
                rows.append(
                    {
                        "lapse_rate": lapse,
                        "true_type": obs.type,
                        "true_severity": obs.severity,
                        "est_type": est.type,
                        "est_severity": est.severity,
                        "confidence": est.confidence,
                        "repeat": rep,
                    }
                )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} simulated sessions -> {args.out}")
    print("lapse  type        detectable range   type acc   sev MAE (when typed right)")
    for lapse in args.lapse_rates:
        for t in ALL_TYPES:
            r = [x for x in rows if x["lapse_rate"] == lapse and x["true_type"] == t]
            if t != "normal":
                r = [x for x in r if x["true_severity"] >= (0.7 if t == "tritan" else 0.4)]
            acc = np.mean([x["est_type"] == t for x in r])
            ok = [x for x in r if x["est_type"] == t]
            mae = np.mean([abs(x["est_severity"] - x["true_severity"]) for x in ok]) if ok else 0
            rng_txt = "-" if t == "normal" else (">= 0.7" if t == "tritan" else ">= 0.4")
            print(f"{lapse:<6} {t:<11} {rng_txt:<18} {acc:8.2f}   {mae:8.3f}")


if __name__ == "__main__":
    main()
