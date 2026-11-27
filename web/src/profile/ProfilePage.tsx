// Profile page: the screening result, what it means, and manual entry. Author: Iris.
import { useId } from "react";

import type { CVDType } from "../api";
import { routeHref } from "../router";
import { typeLabel, type ProfileState } from "./profileStore";

const TYPES: { type: CVDType; short: string; long: string }[] = [
  {
    type: "normal",
    short: "No deficiency found",
    long: "Your answers match typical color vision.",
  },
  {
    type: "protan",
    short: "Less response to red light",
    long: "Your eyes respond less to red light than usual, so some reds, greens, oranges and browns look alike to you, and reds can look darker.",
  },
  {
    type: "deutan",
    short: "Less response to green light",
    long: "Your eyes respond less to green light than usual, so some reds, greens, oranges and browns look alike to you.",
  },
  {
    type: "tritan",
    short: "Less response to blue light",
    long: "Your eyes respond less to blue light than usual, so some blues and greens, and some yellows and pinks, look alike to you.",
  },
];

function CheckIcon() {
  return (
    <svg aria-hidden="true" width="22" height="22" viewBox="0 0 22 22" className="type-mark">
      <circle cx="11" cy="11" r="11" fill="currentColor" />
      <path
        d="M6 11.5l3.2 3.2L16 8"
        fill="none"
        stroke="var(--surface-strong)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface ProfilePageProps {
  state: ProfileState;
  onChange: (next: ProfileState) => void;
}

export function ProfilePage({ state, onChange }: ProfilePageProps) {
  const { profile, source } = state;
  const sevId = useId();
  const info = TYPES.find((t) => t.type === profile.type) ?? TYPES[0]!;
  const isNormal = profile.type === "normal";

  const setType = (type: CVDType) => {
    // A "normal" profile must have severity 0 (CLAUDE.md Section 6).
    const severity = type === "normal" ? 0 : profile.severity || 1;
    onChange({ profile: { type, severity, confidence: 1 }, source: "manual" });
  };

  const setSeverity = (severity: number) =>
    onChange({ profile: { ...profile, severity, confidence: 1 }, source: "manual" });

  return (
    <div className="profile-page">
      <section className="profile-result">
        <div className="profile-heading">
          <h1>{isNormal ? "Typical color vision" : typeLabel(profile.type)}</h1>
          <p className="profile-explain">{info.long}</p>
          {source === "manual" && <p className="muted">You set this profile by hand.</p>}
        </div>

        {source === "example" && (
          <p className="profile-notice">
            This is an example profile, not yours.{" "}
            <a href={routeHref("screening")}>Take the screening</a> to get your own, or set it by
            hand.
          </p>
        )}

        {!isNormal && (
          <div className="severity">
            <div className="severity-row">
              <span>Severity</span>
              <span className="severity-value">{profile.severity.toFixed(1)}</span>
            </div>
            <div
              className="severity-bar"
              role="img"
              aria-label={`Severity ${profile.severity.toFixed(1)} on a scale from 0 to 1`}
            >
              <div style={{ width: `${profile.severity * 100}%` }} />
            </div>
            <div className="severity-scale" aria-hidden="true">
              <span>0 · none</span>
              <span>1 · complete</span>
            </div>
          </div>
        )}

        {source === "screening" && (
          <div className="confidence">
            <span>Confidence in this estimate</span>
            <span className="confidence-value">{profile.confidence.toFixed(1)} of 1</span>
          </div>
        )}

        {source === "example" ? (
          <div className="toolbar">
            <a className="button primary button-lg" href={routeHref("screening")}>
              Take the screening
            </a>
            <a className="profile-retake" href={routeHref("images")}>
              Try the tools with this example
            </a>
          </div>
        ) : (
          <div className="toolbar">
            <a className="button primary button-lg" href={routeHref("images")}>
              Recolor an image
            </a>
            <a className="button button-lg" href={routeHref("live")}>
              Open live webcam
            </a>
            <a className="profile-retake" href={routeHref("screening")}>
              {source === "screening" ? "Retake screening" : "Take the screening"}
            </a>
          </div>
        )}

        <p className="muted">
          This is an estimate, not a medical diagnosis. An eye-care professional can give you a
          clinical test.
        </p>
      </section>

      <section className="profile-manual" aria-labelledby={`${sevId}-h`}>
        <h2 id={`${sevId}-h`}>Change it by hand</h2>
        <p className="muted">
          Use this if you already know your type, or to try how other profiles look.
        </p>
        <fieldset className="type-options">
          <legend>Type</legend>
          {TYPES.map((t) => {
            const selected = t.type === profile.type;
            return (
              <label key={t.type} className="type-option" data-selected={selected || undefined}>
                <input
                  type="radio"
                  name="cvd-type"
                  value={t.type}
                  checked={selected}
                  onChange={() => setType(t.type)}
                />
                {selected ? <CheckIcon /> : <span className="type-mark empty" aria-hidden="true" />}
                <span className="type-text">
                  <span className="type-name">
                    {typeLabel(t.type)}
                    {selected && (source === "screening" ? " · your result" : " · selected")}
                  </span>
                  <span className="type-short">{t.short}</span>
                </span>
              </label>
            );
          })}
        </fieldset>
        <div className="manual-severity">
          <label htmlFor={sevId}>Severity</label>
          <input
            id={sevId}
            type="range"
            min={0.1}
            max={1}
            step={0.1}
            value={isNormal ? 0 : profile.severity}
            disabled={isNormal}
            onChange={(e) => setSeverity(Number(e.target.value))}
          />
          <output htmlFor={sevId}>{isNormal ? "—" : profile.severity.toFixed(1)}</output>
        </div>
      </section>
    </div>
  );
}
