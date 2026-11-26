// Screening test: show plates one at a time, collect answers, score them. Author: Iris.
import { useEffect, useState } from "react";

import {
  getPlates,
  plateImageUrl,
  scoreScreening,
  type CVDProfile,
  type PlateAnswer,
  type PlateMeta,
} from "../api";

const CHOICES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "none"] as const;

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

export function ScreeningView({ onScored }: ScreeningViewProps) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setPhase({ kind: "loading" });
    getPlates(24)
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

  const answer = async (plates: PlateMeta[], answers: PlateAnswer[], value: string) => {
    const plate = plates[answers.length];
    if (!plate) return;
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
  };

  const restart = () => setAttempt((n) => n + 1);

  switch (phase.kind) {
    case "loading":
      return <p>Loading plates…</p>;
    case "scoring":
      return <p>Scoring…</p>;
    case "error":
      return (
        <div>
          <p role="alert">Screening is unavailable: {phase.message}</p>
          <p className="muted">You can still set your color vision by hand above.</p>
          <button onClick={restart}>Try again</button>
        </div>
      );
    case "done":
      return (
        <div>
          <p>
            Result: <strong>{phase.profile.type}</strong>
            {phase.profile.type !== "normal" &&
              `, severity ${phase.profile.severity.toFixed(2)}`}{" "}
            (confidence {Math.round(phase.profile.confidence * 100)}%). Your profile has been
            updated.
          </p>
          <p className="muted">This is a screening aid, not a medical diagnosis.</p>
          <button onClick={restart}>Take the test again</button>
        </div>
      );
    case "answering": {
      const { plates, answers } = phase;
      const plate = plates[answers.length];
      if (!plate) return null;
      return (
        <div className="screening">
          <p>
            Plate {answers.length + 1} of {plates.length}: which number do you see?
          </p>
          <img
            className="plate"
            src={plateImageUrl(plate.plate_id)}
            alt={`Screening plate ${answers.length + 1}`}
            width={320}
            height={320}
          />
          <div className="choices">
            {CHOICES.map((choice) => (
              <button key={choice} onClick={() => void answer(plates, answers, choice)}>
                {choice === "none" ? "I don't see a number" : choice}
              </button>
            ))}
          </div>
        </div>
      );
    }
  }
}
