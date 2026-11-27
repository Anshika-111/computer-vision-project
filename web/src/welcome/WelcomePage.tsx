// Welcome page: what ChromaFix does, a before/after demo, and the way in. Author: Iris.
import { useId, useState } from "react";

import { routeHref } from "../router";
import { DEMO_COLORS, demoView } from "./demoColors";

function ArrowRight() {
  return (
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 22 22">
      <path
        d="M4 11h14m-6-6l6 6-6 6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const STATIONS: { x: number; y: number; big?: boolean }[] = [
  { x: 40, y: 70 },
  { x: 110, y: 70, big: true },
  { x: 280, y: 150 },
  { x: 480, y: 150 },
  { x: 40, y: 270 },
  { x: 110, y: 270, big: true },
  { x: 240, y: 190 },
  { x: 480, y: 110 },
  { x: 110, y: 30 },
  { x: 110, y: 310 },
];

const LABELS: { text: string; x: number; y: number; anchor?: "middle" | "end" }[] = [
  { text: "North", x: 40, y: 50, anchor: "middle" },
  { text: "Harbor", x: 40, y: 300, anchor: "middle" },
  { text: "Hill", x: 132, y: 35 },
  { text: "Docks", x: 132, y: 315 },
  { text: "Market", x: 300, y: 138 },
  { text: "Museum", x: 252, y: 218 },
  { text: "Airport", x: 480, y: 90, anchor: "end" },
  { text: "Central", x: 480, y: 180, anchor: "end" },
];

function Demo() {
  const headingId = useId();
  const [recolored, setRecolored] = useState(false);
  const [simulated, setSimulated] = useState(true);
  const c = DEMO_COLORS[demoView(recolored, simulated)];

  const mapLabel =
    `Transit map with a red, a green and a blue line, ${recolored ? "recolored" : "original colors"}` +
    `${simulated ? ", simulated for deutan vision" : ""}. ` +
    "The green line goes to Airport; the red line goes to Central.";

  return (
    <section className="demo" aria-labelledby={headingId}>
      <div className="demo-head">
        <h2 id={headingId}>Which line goes to Airport?</h2>
        <div className="segmented" role="group" aria-label="Map colors">
          <button type="button" aria-pressed={!recolored} onClick={() => setRecolored(false)}>
            Original
          </button>
          <button type="button" aria-pressed={recolored} onClick={() => setRecolored(true)}>
            Recolored
          </button>
        </div>
      </div>

      <svg className="demo-map" role="img" aria-label={mapLabel} viewBox="0 0 520 340">
        <path d="M110 30 V310" stroke={c.blue} />
        <path d="M40 70 H200 L280 150 H480" stroke={c.red} />
        <path d="M40 270 H160 L240 190 H360 L440 110 H480" stroke={c.green} />
        {STATIONS.map((s) => (
          <circle key={`${s.x},${s.y}`} cx={s.x} cy={s.y} r={s.big ? 11 : 8} />
        ))}
        {LABELS.map((l) => (
          <text key={l.text} x={l.x} y={l.y} textAnchor={l.anchor ?? "start"}>
            {l.text}
          </text>
        ))}
      </svg>

      <label className="demo-toggle">
        <input
          type="checkbox"
          checked={simulated}
          onChange={(e) => setSimulated(e.target.checked)}
        />
        Show it as a person with deutan color vision sees it
      </label>

      <div className="demo-readout" aria-live="polite">
        <span className="demo-number">{c.redGreenDe00.toFixed(1)}</span>
        <span>
          Color difference between the red and green lines (CIEDE2000),{" "}
          {simulated ? "as seen with simulated deutan vision" : "as seen with typical color vision"}
          . Higher is easier to tell apart.
        </span>
      </div>
    </section>
  );
}

export function WelcomePage() {
  return (
    <div className="app welcome">
      <header className="app-header welcome-header">
        <span className="wordmark">ChromaFix</span>
        <a className="welcome-skip" href={routeHref("images")}>
          Skip to the tools
        </a>
      </header>

      <main className="welcome-main">
        <div className="welcome-hero">
          <section className="welcome-intro">
            <h1>Tell apart the colors you mix up.</h1>
            <p className="welcome-lede">
              A short dot-plate screening estimates your type of color vision deficiency and how
              strong it is. ChromaFix then recolors photos and your webcam view for that profile.
            </p>
            <div className="welcome-actions">
              <a className="button primary button-lg" href={routeHref("screening")}>
                Start screening
                <ArrowRight />
              </a>
              <a className="button button-lg" href={routeHref("games")}>
                I have a participant ID
              </a>
            </div>
            <p className="muted">24 plates. Type the number you see, or say you see none.</p>
          </section>
          <Demo />
        </div>

        <dl className="welcome-facts">
          <div>
            <dt>Built for your result</dt>
            <dd>
              Recoloring is tuned to the type and severity your screening finds, not one correction
              for everyone.
            </dd>
          </div>
          <div>
            <dt>Your images stay yours</dt>
            <dd>Uploads are recolored and not stored. Webcam video is processed in your browser.</dd>
          </div>
          <div>
            <dt>An estimate, not a diagnosis</dt>
            <dd>
              ChromaFix is a class research project. An eye-care professional can give you a
              clinical test.
            </dd>
          </div>
        </dl>
      </main>

      <footer className="welcome-footer">
        <span>CS 4391 Computer Vision · Group 6</span>
        <span>
          Map colors computed with Machado et al. 2009 simulation and Fidaner et al. 2005
          daltonization, deutan severity 1.0.
        </span>
      </footer>
    </div>
  );
}
