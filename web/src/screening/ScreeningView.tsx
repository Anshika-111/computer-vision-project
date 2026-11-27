// Screening test: show plates one at a time, collect answers, score them. Author: Iris.
import { useCallback, useEffect, useRef, useState } from "react";

import {
  getPlates,
  plateImageUrl,
  scoreScreening,
  type CVDProfile,
  type PlateAnswer,
  type PlateMeta,
} from "../api";
import { routeHref } from "../router";

const PLATE_COUNT = 24;
/** Plates are generated at 512 px; showing them at native size avoids resampling. */
const PLATE_PX = 512;
const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"] as const;

interface ScreeningViewProps {
  onScored: (profile: CVDProfile) => void;
}

type Phase =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "answering"; plates: PlateMeta[]; answers: PlateAnswer[] }
  | { kind: "scoring" }
  | { kind: "done"; profile: CVDProfile };

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function typeName(profile: CVDProfile): string {
  return profile.type.charAt(0).toUpperCase() + profile.type.slice(1);
}

/** Map a key press to an answer: digits, or N for "no number". */
function keyToAnswer(event: KeyboardEvent): string | null {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return null;
  const target = event.target as HTMLElement | null;
  if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return null;
  if (/^[0-9]$/.test(event.key)) return event.key;
  if (event.key === "n" || event.key === "N") return "none";
  return null;
}

export function ScreeningView({ onScored }: ScreeningViewProps) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Plate already answered; stops a fast double key press from answering it twice.
  const answeredRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPhase({ kind: "loading" });
    answeredRef.current = null;
    getPlates(PLATE_COUNT)
      .then((plates) => {
        if (!cancelled) setPhase({ kind: "answering", plates, answers: [] });
      })
      .catch((error: unknown) => {
        if (!cancelled) setPhase({ kind: "error", message: message(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const answer = useCallback(
    async (value: string) => {
      if (phase.kind !== "answering") return;
      const { plates, answers } = phase;
      const plate = plates[answers.length];
      if (!plate || answeredRef.current === plate.plate_id) return;
      answeredRef.current = plate.plate_id;
      const next = [...answers, { plate_id: plate.plate_id, answer: value }];
      if (next.length < plates.length) {
        setPhase({ kind: "answering", plates, answers: next });
        return;
      }
      setPhase({ kind: "scoring" });
      try {
        const profile = await scoreScreening(next);
        setPhase({ kind: "done", profile });
        onScored(profile);
      } catch (error) {
        setPhase({ kind: "error", message: message(error) });
      }
    },
    [phase, onScored],
  );

  // Number keys and N answer the current plate.
  useEffect(() => {
    if (phase.kind !== "answering") return;
    const onKey = (event: KeyboardEvent) => {
      const value = keyToAnswer(event);
      if (value === null) return;
      event.preventDefault();
      void answer(value);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase.kind, answer]);

  // Move focus to the question on each new plate so screen readers announce it.
  const plateIndex = phase.kind === "answering" ? phase.answers.length : -1;
  useEffect(() => {
    if (plateIndex >= 0) headingRef.current?.focus();
  }, [plateIndex]);

  const restart = () => setAttempt((n) => n + 1);

  switch (phase.kind) {
    case "loading":
      return (
        <section className="screening-status" aria-busy="true">
          <h1>Screening</h1>
          <p>Loading plates…</p>
        </section>
      );
    case "scoring":
      return (
        <section className="screening-status" aria-busy="true">
          <h1>Screening</h1>
          <p>Working out your result…</p>
        </section>
      );
    case "error":
      return (
        <section className="screening-status">
          <h1>Screening</h1>
          <p role="alert">Screening is unavailable: {phase.message}</p>
          <p className="muted">
            Check that the ChromaFix server is running, then try again. You can also set your
            color vision by hand on the <a href={routeHref("images")}>Image</a> page.
          </p>
          <div className="toolbar">
            <button type="button" className="primary" onClick={restart}>
              Try again
            </button>
          </div>
        </section>
      );
    case "done": {
      const { profile } = phase;
      return (
        <section className="screening-status">
          <h1>
            {profile.type === "normal"
              ? "No color vision deficiency found"
              : `${typeName(profile)}, severity ${profile.severity.toFixed(1)}`}
          </h1>
          <p>
            Confidence in this estimate: {profile.confidence.toFixed(1)} of 1. Your profile is
            saved for the image and live views.
          </p>
          <div className="toolbar">
            <a className="button primary" href={routeHref("images")}>
              Recolor an image
            </a>
            <a className="button" href={routeHref("live")}>
              Open live webcam
            </a>
            <button type="button" onClick={restart}>
              Retake screening
            </button>
          </div>
          <p className="muted">
            This is an estimate, not a medical diagnosis. An eye-care professional can give you a
            clinical test.
          </p>
        </section>
      );
    }
    case "answering": {
      const { plates, answers } = phase;
      const plate = plates[answers.length];
      if (!plate) return null;
      const n = answers.length + 1;
      return (
        <section className="screening">
          <div className="screening-progress">
            <div className="screening-progress-text">
              <span>
                Plate {n} of {plates.length}
              </span>
              <a href={routeHref("welcome")}>Stop screening</a>
            </div>
            <progress
              value={answers.length}
              max={plates.length}
              aria-label={`${answers.length} of ${plates.length} plates answered`}
            />
          </div>

          <div className="screening-body">
            <img
              key={plate.plate_id}
              className="plate"
              src={plateImageUrl(plate.plate_id)}
              alt={`Dot-pattern plate ${n} with a hidden number`}
              width={PLATE_PX}
              height={PLATE_PX}
            />
            <div className="screening-answer">
              <h1 ref={headingRef} tabIndex={-1}>
                What number do you see?
              </h1>
              <div className="numpad" role="group" aria-label="Number you see">
                {DIGITS.map((d) => (
                  <button key={d} type="button" onClick={() => void answer(d)}>
                    {d}
                  </button>
                ))}
              </div>
              <button type="button" className="no-number" onClick={() => void answer("none")}>
                I don't see a number
              </button>
              <p className="muted">
                You can also press a number key, or N for no number. Answer with your first
                impression. There is no going back to earlier plates.
              </p>
            </div>
          </div>
        </section>
      );
    }
  }
}
