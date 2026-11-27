// Mini-games (color match, ripe fruit): pick the outlined region that answers the prompt, log
// every trial. One session plays every game back to back. Author: Iris.
import { useCallback, useEffect, useId, useRef, useState } from "react";

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
import { profileLabel } from "../profile/profileStore";
import { routeHref } from "../router";

/** Games in one session. Answer keys live in server/games/<id>.json. */
const GAMES = [
  { id: "color_match", title: "Color match" },
  { id: "ripe_fruit", title: "Ripe fruit" },
] as const;

/** Odd participant numbers play the games in listed order, even numbers in reverse,
 * so neither game is always played first (when players are fresher or less practiced). */
function gameOrder(participantId: string): (typeof GAMES)[number][] {
  const odd = Number(participantId.slice(1)) % 2 === 1;
  return odd ? [...GAMES] : [...GAMES].reverse();
}

/** A server trial plus the game it belongs to (trial_id is unique only within a game). */
interface SessionTrial extends GameTrial {
  game: string;
  gameTitle: string;
}

const CONDITION_LABELS: Record<Method, string> = {
  none: "No recoloring",
  fixed: "Fixed daltonization",
  personalized: "Personalized",
  neural: "Neural",
};

interface GamesViewProps {
  profile: CVDProfile;
  /** True while the app only has the example profile; sessions must not log it. */
  profileIsExample: boolean;
}

interface TrialResult {
  condition: Method;
  correct: boolean;
  rtMs: number;
}

interface Session {
  sessionId: string;
  participantId: string;
  /** Locked when the session starts, so changing the profile mid-game has no effect. */
  profile: CVDProfile;
  simulateView: boolean;
  trials: SessionTrial[];
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
async function prepareImage(trial: SessionTrial, session: Session): Promise<string> {
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

export function GamesView({ profile, profileIsExample }: GamesViewProps) {
  const ids = useId();
  const [participantId, setParticipantId] = useState("");
  // Off by default: a participant with CVD must see the recolored image directly.
  // Simulation is only for demos to viewers with typical color vision.
  const [simulateView, setSimulateView] = useState(false);
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
      const order = gameOrder(participantId);
      const lists = await Promise.all(
        order.map(async (g) =>
          (await getGameTrials(g.id, participantId)).map((t) => ({
            ...t,
            game: g.id,
            gameTitle: g.title,
          })),
        ),
      );
      const trials: SessionTrial[] = lists.flat();
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

  const answer = useCallback((side: GameSide) => {
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
      game: trial.game,
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
  }, [session, trial]);

  // A and B keys answer the current round once its image is showing.
  useEffect(() => {
    if (!trial || !size) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) return;
      const side = event.key.toLowerCase();
      if ((side === "a" || side === "b") && trial.options.includes(side)) {
        event.preventDefault();
        answer(side);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [trial, size, answer]);

  if (!session || done) {
    const idInvalid = participantId !== "" && !participantValid;
    return (
      <section className="game-setup">
        {done ? (
          <>
            <h1>Session complete</h1>
            <p>
              Thank you. All {session.trials.length} rounds are saved under participant{" "}
              {session.participantId}.
            </p>
            <ResultsTable results={results} />
          </>
        ) : (
          <>
            <h1>Mini-games</h1>
            <p>
              Two short games, {GAMES.map((g) => g.title).join(" and ")}, played one after the
              other.
            </p>
            <ol className="game-steps">
              <li>Each round shows one image with two outlined regions, labeled A and B.</li>
              <li>Read the question above the image.</li>
              <li>
                Click <strong>A</strong> or <strong>B</strong>, or press the A or B key. Answer as
                quickly as you can while staying accurate.
              </li>
            </ol>
            <p className="muted">
              Rounds use different recoloring methods. The next round starts right after you
              answer.
            </p>
          </>
        )}

        {profileIsExample ? (
          <p role="alert">
            You need a profile before starting. <a href={routeHref("screening")}>Take the
            screening</a>, or set your type on the <a href={routeHref("profile")}>profile</a> page.
          </p>
        ) : (
          <div className="game-profile">
            <span>
              Profile for every round: <strong>{profileLabel(profile)}</strong>
            </span>
            <a href={routeHref("profile")}>Change</a>
          </div>
        )}
        {!profileIsExample && profile.type === "normal" && (
          <p role="alert">
            Your profile is typical color vision, so every method shows the same image. Pick a CVD
            type on your <a href={routeHref("profile")}>profile</a> page for the demo.
          </p>
        )}

        <form
          className="game-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (participantValid && !starting) void start();
          }}
        >
          <div className="field">
            <label className="field-label" htmlFor={`${ids}-pid`}>
              Participant ID
            </label>
            <input
              id={`${ids}-pid`}
              value={participantId}
              onChange={(e) => setParticipantId(e.target.value.trim().toUpperCase())}
              placeholder="P07"
              autoComplete="off"
              spellCheck={false}
              size={8}
              aria-invalid={idInvalid}
              aria-describedby={`${ids}-pid-hint`}
            />
            <span id={`${ids}-pid-hint`} className={idInvalid ? "field-error" : "muted"}>
              {idInvalid
                ? "Use P followed by up to 4 digits, like P07."
                : "The anonymous ID you were given, like P07. No names are stored."}
            </span>
          </div>
          <label className="game-sim">
            <input
              type="checkbox"
              checked={simulateView}
              onChange={(e) => setSimulateView(e.target.checked)}
            />
            Demo only: simulate this profile, for viewers with typical color vision
          </label>
          <button
            type="submit"
            className="primary button-lg"
            disabled={!participantValid || starting || profileIsExample}
          >
            {starting ? "Loading rounds…" : done ? "Start another session" : "Start"}
          </button>
        </form>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  const total = session.trials.length;
  return (
    <section className="game">
      <div className="screening-progress">
        <div className="screening-progress-text">
          <span>
            {trial!.gameTitle} · Round {index + 1} of {total} · Participant{" "}
            {session.participantId}
          </span>
          <a
            href={routeHref("games")}
            onClick={(e) => {
              e.preventDefault();
              setSession(null);
            }}
          >
            Leave session
          </a>
        </div>
        <progress value={index} max={total} aria-label={`${index} of ${total} rounds answered`} />
      </div>

      <h1 className="game-prompt">{trial!.prompt}</h1>

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
          <p className="game-loading">Loading the image…</p>
        )}
      </div>

      <div className="answer-buttons" role="group" aria-label="Your answer">
        {trial!.options.map((side) => (
          <button key={side} type="button" onClick={() => answer(side)} disabled={!size}>
            {side.toUpperCase()}
          </button>
        ))}
      </div>
      <p className="muted game-hint">Click A or B, or press the A or B key.</p>

      {error && (
        <div className="toolbar">
          <p role="alert">{error}</p>
          {!imageUrl && (
            <button
              type="button"
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
