// Color-match mini-game: pick the outlined region that answers the prompt, log every trial. Author: Iris.
import { useEffect, useRef, useState } from "react";

import {
  getGameImage,
  getGameTrials,
  postLog,
  recolorImage,
  simulateImage,
  type CVDProfile,
  type GameSide,
  type GameTrial,
  type Method,
} from "../api";

const GAME = "color_match";

const CONDITION_LABELS: Record<Method, string> = {
  none: "No recoloring",
  fixed: "Fixed daltonization",
  personalized: "Personalized",
  neural: "Neural",
};

interface GamesViewProps {
  profile: CVDProfile;
}

interface TrialResult {
  condition: Method;
  correct: boolean;
  rtMs: number;
}

interface Session {
  sessionId: string;
  participantId: string;
  /** Locked when the session starts, so changing the profile bar mid-game has no effect. */
  profile: CVDProfile;
  simulateView: boolean;
  trials: GameTrial[];
}

/** e.g. s_20261127_142305 (local time). Matches the server's safe-id pattern. */
function newSessionId(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  const time = `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  return `s_${date}_${time}`;
}

/** The image the player sees: recolored for the trial's condition, then optionally simulated. */
async function prepareImage(trial: GameTrial, session: Session): Promise<string> {
  const original = await getGameImage(trial.image_id);
  const recolored = await recolorImage(original, session.profile, trial.condition);
  // Recolor first, then simulate (S @ R): how a viewer with this profile sees the result.
  const shown = session.simulateView ? await simulateImage(recolored, session.profile) : recolored;
  return URL.createObjectURL(shown);
}

function centroid(points: [number, number][]): [number, number] {
  const sum = points.reduce(([sx, sy], [x, y]) => [sx + x, sy + y], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}

export function GamesView({ profile }: GamesViewProps) {
  const [participantId, setParticipantId] = useState("P01");
  const [simulateView, setSimulateView] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<TrialResult[]>([]);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Image URLs being prepared, by trial index, so the next trial loads while this one shows.
  const prepared = useRef(new Map<number, Promise<string>>());
  const shownAt = useRef<number | null>(null);

  const participantValid = /^P\d{1,4}$/.test(participantId);
  const done = session !== null && index >= session.trials.length;
  const trial = session && !done ? session.trials[index] : null;

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const trials = await getGameTrials(GAME, participantId);
      prepared.current.forEach((p) => p.then(URL.revokeObjectURL, () => undefined));
      prepared.current = new Map();
      setResults([]);
      setIndex(0);
      setSession({ sessionId: newSessionId(), participantId, profile, simulateView, trials });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setStarting(false);
    }
  };

  // Load the current trial's image and start preparing the next one.
  useEffect(() => {
    if (!session || done) return;
    let cancelled = false;
    const ensure = (i: number) => {
      const next = session.trials[i];
      if (next && !prepared.current.has(i)) {
        prepared.current.set(i, prepareImage(next, session));
      }
    };
    ensure(index);
    ensure(index + 1);
    setImageUrl(null);
    setSize(null);
    shownAt.current = null;
    prepared.current
      .get(index)!
      .then((url) => {
        if (!cancelled) setImageUrl(url);
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [session, index, done]);

  // Free every prepared image when the component unmounts.
  useEffect(() => {
    const map = prepared.current;
    return () => map.forEach((p) => p.then(URL.revokeObjectURL, () => undefined));
  }, []);

  const answer = (side: GameSide) => {
    if (!session || !trial || shownAt.current === null) return;
    const rtMs = Math.round(performance.now() - shownAt.current);
    // One answer per trial, even on a fast double click.
    shownAt.current = null;
    const correct = side === trial.correct_answer;
    setResults((r) => [...r, { condition: trial.condition, correct, rtMs }]);
    postLog({
      session_id: session.sessionId,
      participant_id: session.participantId,
      profile: session.profile,
      game: GAME,
      trial_id: trial.trial_id,
      image_id: trial.image_id,
      condition: trial.condition,
      answer: side,
      correct,
      rt_ms: rtMs,
      timestamp: new Date().toISOString(),
    }).catch((cause) =>
      setError(`Trial was not logged: ${cause instanceof Error ? cause.message : cause}`),
    );
    setIndex((i) => i + 1);
  };

  if (!session || done) {
    return (
      <section className="game">
        <h2>Color match</h2>
        <p>
          Each round shows an image with two outlined regions, A and B. Pick the one that answers
          the question as fast as you can. Rounds use different recoloring methods.
        </p>
        {profile.type === "normal" && (
          <p role="alert">
            Your profile is normal vision, so every method shows the same image. Pick a CVD type
            in the profile bar for the demo.
          </p>
        )}
        <div className="toolbar">
          <label>
            Participant ID{" "}
            <input
              value={participantId}
              onChange={(e) => setParticipantId(e.target.value.trim())}
              size={6}
              aria-invalid={!participantValid}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={simulateView}
              onChange={(e) => setSimulateView(e.target.checked)}
            />{" "}
            Show images as a viewer with this profile sees them
          </label>
          <button onClick={() => void start()} disabled={!participantValid || starting}>
            {done ? "Play again" : "Start"}
          </button>
        </div>
        <p className="muted">Use an anonymous ID like P07. No names are stored.</p>
        {error && <p role="alert">{error}</p>}
        {done && <ResultsTable results={results} />}
      </section>
    );
  }

  return (
    <section className="game">
      <p className="muted">
        Round {index + 1} of {session.trials.length}
      </p>
      <h2>{trial!.prompt}</h2>
      <div className="game-stage">
        {imageUrl ? (
          <>
            <img
              src={imageUrl}
              alt="Game image with regions A and B outlined"
              onLoad={(e) => {
                setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight });
                shownAt.current = performance.now();
              }}
            />
            {size && (
              <svg viewBox={`0 0 ${size.w} ${size.h}`} aria-hidden="true">
                {(["a", "b"] as const).map((side) => {
                  const points = trial!.polygons[side];
                  const [cx, cy] = centroid(points);
                  const pts = points.map(([x, y]) => `${x},${y}`).join(" ");
                  return (
                    <g key={side}>
                      <polygon className="outline-dark" points={pts} />
                      <polygon points={pts} />
                      <text
                        x={cx}
                        y={cy}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        fontSize={size.w / 18}
                      >
                        {side.toUpperCase()}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </div>
      <div className="answer-buttons">
        {trial!.options.map((side) => (
          <button key={side} onClick={() => answer(side)} disabled={!size}>
            {side.toUpperCase()}
          </button>
        ))}
      </div>
      {error && (
        <div>
          <p role="alert">{error}</p>
          {!imageUrl && (
            <button
              onClick={() => {
                // Not logged: the player never saw this round.
                setError(null);
                setIndex((i) => i + 1);
              }}
            >
              Skip this round
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function ResultsTable({ results }: { results: TrialResult[] }) {
  const byCondition = new Map<Method, TrialResult[]>();
  results.forEach((r) => byCondition.set(r.condition, [...(byCondition.get(r.condition) ?? []), r]));
  return (
    <table className="results">
      <caption>Your results</caption>
      <thead>
        <tr>
          <th>Condition</th>
          <th>Rounds</th>
          <th>Accuracy</th>
          <th>Mean time</th>
        </tr>
      </thead>
      <tbody>
        {[...byCondition].map(([condition, rows]) => {
          const accuracy = rows.filter((r) => r.correct).length / rows.length;
          const meanRt = rows.reduce((s, r) => s + r.rtMs, 0) / rows.length;
          return (
            <tr key={condition}>
              <td>{CONDITION_LABELS[condition]}</td>
              <td>{rows.length}</td>
              <td>{Math.round(accuracy * 100)}%</td>
              <td>{(meanRt / 1000).toFixed(2)} s</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
