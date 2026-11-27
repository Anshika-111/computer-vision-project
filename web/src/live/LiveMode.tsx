// Live webcam mode: view, type, severity and method controls around the shader. Author: Iris.
// Type and severity here are a local override for trying other profiles; they never
// change the saved profile. "Reset to my profile" returns to it.
import { useEffect, useId, useState } from "react";

import {
  getMethods,
  getRecolorMatrix,
  getSimulationMatrix,
  type CVDProfile,
  type CVDType,
  type Mat3,
  type MatrixMethod,
} from "../api";
import { typeLabel } from "../profile/profileStore";
import { LiveView } from "./LiveView";
import { IDENTITY, simulateAfterRecolor } from "./matrix";

type View = "original" | "simulated" | "recolored" | "recolored-seen";
type CvdOnly = Exclude<CVDType, "normal">;

const CVD_TYPES: CvdOnly[] = ["protan", "deutan", "tritan"];
const METHOD_LABELS: Record<MatrixMethod, string> = {
  none: "None",
  fixed: "Fixed",
  personalized: "Personalized",
};

interface LiveModeProps {
  profile: CVDProfile;
}

interface Settings {
  type: CvdOnly;
  severity: number;
}

/** A normal-vision profile has nothing to simulate, so live mode starts from deutan 1.0. */
function fromProfile(profile: CVDProfile): Settings {
  return profile.type === "normal"
    ? { type: "deutan", severity: 1 }
    : { type: profile.type, severity: profile.severity };
}

async function matrixFor(view: View, s: Settings, method: MatrixMethod): Promise<Mat3> {
  switch (view) {
    case "original":
      return IDENTITY;
    case "simulated":
      return getSimulationMatrix(s.type, s.severity);
    case "recolored":
      return getRecolorMatrix(method, s.type, s.severity);
    case "recolored-seen": {
      const [sim, rec] = await Promise.all([
        getSimulationMatrix(s.type, s.severity),
        getRecolorMatrix(method, s.type, s.severity),
      ]);
      return simulateAfterRecolor(sim, rec); // S @ R: recolor first, then simulate
    }
  }
}

function caption(view: View, s: Settings, method: MatrixMethod): string {
  const who = `${s.type} ${s.severity.toFixed(1)}`;
  const how = METHOD_LABELS[method].toLowerCase();
  switch (view) {
    case "original":
      return "Original";
    case "simulated":
      return `Simulated · how ${who} sees it`;
    case "recolored":
      return `Recolored · ${how} for ${who}`;
    case "recolored-seen":
      return `Recolored · ${how}, as ${who} sees it`;
  }
}

export function LiveMode({ profile }: LiveModeProps) {
  const ids = useId();
  const [cameraOn, setCameraOn] = useState(false);
  const [view, setView] = useState<View>("recolored");
  const [settings, setSettings] = useState<Settings>(() => fromProfile(profile));
  // Neural has no matrix form, so live mode only offers matrix methods.
  const [methods, setMethods] = useState<MatrixMethod[]>(["fixed"]);
  const [method, setMethod] = useState<MatrixMethod>("fixed");
  const [matrix, setMatrix] = useState<Mat3>(IDENTITY);
  const [error, setError] = useState<string | null>(null);

  const mine = fromProfile(profile);
  const isMine = mine.type === settings.type && mine.severity === settings.severity;
  const usesMethod = view === "recolored" || view === "recolored-seen";

  // Follow the saved profile when it changes elsewhere.
  useEffect(() => setSettings(fromProfile(profile)), [profile]);

  useEffect(() => {
    getMethods()
      .then((available) => {
        const usable = available.filter(
          (m): m is MatrixMethod => m === "fixed" || m === "personalized",
        );
        if (usable.length === 0) return;
        setMethods(usable);
        setMethod(usable.includes("personalized") ? "personalized" : usable[0]!);
      })
      .catch(() => undefined); // keep the "fixed" default
  }, []);

  useEffect(() => {
    let cancelled = false;
    matrixFor(view, settings, method)
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
  }, [view, settings, method]);

  const views: { value: View; label: string }[] = [
    { value: "original", label: "Original" },
    { value: "simulated", label: `Simulated: how ${settings.type} sees it` },
    { value: "recolored", label: "Recolored" },
    { value: "recolored-seen", label: "Recolored, then simulated" },
  ];

  return (
    <div className="live-page">
      <section className="live-stage">
        <div className="live-stage-head">
          <h1>{caption(view, settings, method)}</h1>
          {cameraOn && (
            <button type="button" onClick={() => setCameraOn(false)}>
              Turn off camera
            </button>
          )}
        </div>

        {cameraOn ? (
          <LiveView matrix={matrix} />
        ) : (
          <div className="live-off">
            <p className="live-off-title">See your surroundings through the selected view.</p>
            <button type="button" className="primary button-lg" onClick={() => setCameraOn(true)}>
              Turn on camera
            </button>
            <p className="muted">Your browser will ask for permission first.</p>
          </div>
        )}

        {error && <p role="alert">Couldn't load the color matrix: {error}</p>}
        <p className="muted">Video is processed in your browser. Nothing is recorded or uploaded.</p>
      </section>

      <aside className="live-panel" aria-label="Live view settings">
        <fieldset className="live-views">
          <legend>View</legend>
          {views.map((v) => (
            <label key={v.value} data-selected={v.value === view || undefined}>
              <input
                type="radio"
                name={`${ids}-view`}
                checked={v.value === view}
                onChange={() => setView(v.value)}
              />
              {v.label}
            </label>
          ))}
        </fieldset>

        <div className="field">
          <label className="field-label" htmlFor={`${ids}-type`}>
            Type
          </label>
          <select
            id={`${ids}-type`}
            value={settings.type}
            onChange={(e) => setSettings({ ...settings, type: e.target.value as CvdOnly })}
          >
            {CVD_TYPES.map((t) => (
              <option key={t} value={t}>
                {typeLabel(t)}
                {profile.type === t ? " (your profile)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <div className="live-sev-row">
            <label className="field-label" htmlFor={`${ids}-sev`}>
              Severity
            </label>
            <output htmlFor={`${ids}-sev`}>{settings.severity.toFixed(1)}</output>
          </div>
          <input
            id={`${ids}-sev`}
            type="range"
            min={0.1}
            max={1}
            step={0.1}
            value={settings.severity}
            onChange={(e) => setSettings({ ...settings, severity: Number(e.target.value) })}
          />
        </div>

        <div className="field">
          <span className="field-label" id={`${ids}-m`}>
            Recoloring method
          </span>
          <div className="segmented segmented-fill" role="group" aria-labelledby={`${ids}-m`}>
            {methods.map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={m === method}
                disabled={!usesMethod}
                onClick={() => setMethod(m)}
              >
                {METHOD_LABELS[m]}
              </button>
            ))}
          </div>
          <span className="muted">
            {usesMethod
              ? "Neural recoloring works on still images only."
              : "Used by the recolored views."}
          </span>
        </div>

        {profile.type !== "normal" && (
          <button
            type="button"
            disabled={isMine}
            onClick={() => setSettings(fromProfile(profile))}
          >
            {isMine ? "Showing your profile" : "Reset to my profile"}
          </button>
        )}
      </aside>
    </div>
  );
}
