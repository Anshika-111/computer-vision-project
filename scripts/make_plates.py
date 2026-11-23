"""Generate, validate, and save screening plates (PNG + plates.json). Author: Avneet."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from chromafix.color import save_image
from chromafix.constants import SEED
from chromafix.screening import generate_plates, render_plate, validate_plates


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-per-type-level", type=int, default=10, help="plates per type × level")
    ap.add_argument("--n-controls", type=int, default=6)
    ap.add_argument("--size", type=int, default=512, help="PNG width/height in pixels")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=Path("data/plates"))
    args = ap.parse_args()

    raw = generate_plates(args.n_per_type_level, seed=args.seed, n_controls=args.n_controls)
    plates = validate_plates(raw)
    args.out.mkdir(parents=True, exist_ok=True)
    for plate in plates:
        save_image(args.out / f"{plate.plate_id}.png", render_plate(plate, size=args.size))
    (args.out / "plates.json").write_text(json.dumps([p.to_dict() for p in plates], indent=2))

    print(f"generated {len(raw)}, kept {len(plates)} after validation -> {args.out}")
    for (t, d), n in sorted(Counter((p.target_type, p.difficulty) for p in plates).items()):
        print(f"  {t:7s} level {d}: {n}")


if __name__ == "__main__":
    main()
