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
import { useFocusMode } from "../focusMode";
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
  | { kind: "scoring" };

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
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
        // The parent saves the profile and opens the profile page.
        onScored(await scoreScreening(next));
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

  // On phones, hide the nav while plates are showing: more room, and no stray taps away.
  useFocusMode(phase.kind === "answering");

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
            color vision by hand on your <a href={routeHref("profile")}>profile</a> page.
          </p>
          <div className="toolbar">
            <button type="button" className="primary" onClick={restart}>
              Try again
            </button>
          </div>
        </section>
      );
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
                <span className="hint-keys">
                  You can also press a number key, or N for no number.{" "}
                </span>
                Answer with your first impression. There is no going back to earlier plates.
              </p>
            </div>
          </div>
        </section>
      );
    }
  }
}
