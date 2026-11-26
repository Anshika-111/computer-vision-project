// Live webcam mode driven by the user's profile: picks the view, fetches matrices. Author: Iris.
import { useEffect, useState } from "react";

import {
  getMethods,
  getRecolorMatrix,
  getSimulationMatrix,
  type CVDProfile,
  type Mat3,
  type MatrixMethod,
} from "../api";
import { LiveView } from "./LiveView";
import { IDENTITY, simulateAfterRecolor } from "./matrix";

type View = "original" | "simulated" | "recolored" | "recolored-seen";

const VIEWS: { value: View; label: string }[] = [
  { value: "original", label: "Original" },
  { value: "simulated", label: "As you see it (simulated)" },
  { value: "recolored", label: "Recolored" },
  { value: "recolored-seen", label: "Recolored, as you see it" },
];

interface LiveModeProps {
  profile: CVDProfile;
}

async function matrixFor(view: View, profile: CVDProfile, method: MatrixMethod): Promise<Mat3> {
  const { type, severity } = profile;
  switch (view) {
    case "original":
      return IDENTITY;
    case "simulated":
      return getSimulationMatrix(type, severity);
    case "recolored":
      return getRecolorMatrix(method, type, severity);
    case "recolored-seen": {
      const [s, r] = await Promise.all([
        getSimulationMatrix(type, severity),
        getRecolorMatrix(method, type, severity),
      ]);
      return simulateAfterRecolor(s, r); // S @ R: recolor first, then simulate
    }
  }
}

export function LiveMode({ profile }: LiveModeProps) {
  const [view, setView] = useState<View>("recolored");
  // Neural has no matrix form, so live mode only offers matrix methods.
  const [methods, setMethods] = useState<MatrixMethod[]>(["fixed"]);
  const [method, setMethod] = useState<MatrixMethod>("fixed");
  const [matrix, setMatrix] = useState<Mat3>(IDENTITY);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMethods()
      .then((available) => {
        const usable = available.filter(
          (m): m is MatrixMethod => m === "fixed" || m === "personalized",
        );
        if (usable.length > 0) setMethods(usable);
      })
      .catch(() => undefined); // keep the "fixed" default
  }, []);

  useEffect(() => {
    let cancelled = false;
    matrixFor(view, profile, method)
      .then((m) => {
        if (cancelled) return;
        setMatrix(m);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [view, profile, method]);

  return (
    <section>
      <div className="toolbar">
        <label>
          View{" "}
          <select value={view} onChange={(e) => setView(e.target.value as View)}>
            {VIEWS.map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
          </select>
        </label>
        {(view === "recolored" || view === "recolored-seen") && (
          <label>
            Method{" "}
            <select value={method} onChange={(e) => setMethod(e.target.value as MatrixMethod)}>
              {methods.map((m) => (
                <option key={m} value={m}>
                  {m === "fixed" ? "Fixed daltonization" : "Personalized"}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {error && <p role="alert">Could not load the color matrix: {error}</p>}
      <LiveView matrix={matrix} />
    </section>
  );
}
