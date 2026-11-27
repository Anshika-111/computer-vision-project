// Fixed colors and CIEDE2000 values for the Welcome page transit-map demo. Author: Iris.
//
// Every value below was produced by the team's Python pipeline, not computed in the
// browser, so the page shows exactly what chromafix outputs and needs no second
// color-difference implementation (CLAUDE.md Section 11, rule 3).
//
// Regenerate (from the repo root, with the project venv):
//
//   import numpy as np
//   from chromafix.color import srgb_to_linear, linear_to_srgb, linear_to_lab, delta_e00
//   from chromafix.simulate import simulate
//   from chromafix.recolor import recolor
//   from chromafix.profile import CVDProfile
//   p = CVDProfile("deutan", 1.0, 1.0)
//   # for each line color L (linear, shape (1, 1, 3)):
//   #   sim = simulate(L, "deutan", 1.0)
//   #   rec = recolor(L, p, "fixed")
//   #   rec_sim = simulate(rec, "deutan", 1.0)
//   # hex = linear_to_srgb(x) rounded to 8 bits; de = delta_e00(linear_to_lab(a), linear_to_lab(b))
//
// Method is "fixed" at deutan severity 1.0 because personalized parameters are not tuned
// yet. Swap to "personalized" once chromafix/recolor/params/personalized.json exists.

export interface LineColors {
  red: string;
  green: string;
  blue: string;
  /** CIEDE2000 between the red and green lines in this view. */
  redGreenDe00: number;
}

export type DemoView = "original" | "originalSimulated" | "recolored" | "recoloredSimulated";

export const DEMO_COLORS: Record<DemoView, LineColors> = {
  original: { red: "#D1452F", green: "#3E9A44", blue: "#2F6DB5", redGreenDe00: 62.7 },
  originalSimulated: { red: "#908129", green: "#91854A", blue: "#3666B4", redGreenDe00: 5.3 },
  recolored: { red: "#D16C92", green: "#3E8900", blue: "#2F72B5", redGreenDe00: 67.4 },
  recoloredSimulated: { red: "#95938F", green: "#84761A", blue: "#3E69B4", redGreenDe00: 24.3 },
};

export function demoView(recolored: boolean, simulated: boolean): DemoView {
  if (recolored) return simulated ? "recoloredSimulated" : "recolored";
  return simulated ? "originalSimulated" : "original";
}
