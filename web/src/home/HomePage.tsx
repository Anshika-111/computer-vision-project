// In-app home: where the user is in the screening -> profile -> recolor flow. Author: Iris.
import type { CVDProfile } from "../api";
import { profileLabel, type ProfileSource } from "../profile/profileStore";
import { routeHref } from "../router";

interface HomePageProps {
  profile: CVDProfile;
  source: ProfileSource;
}

type StepState = "done" | "next" | "later";

function StepMark({ n, state }: { n: number; state: StepState }) {
  if (state === "done") {
    return (
      <svg aria-hidden="true" width="32" height="32" viewBox="0 0 22 22" className="step-mark">
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
  return (
    <span className="step-mark step-num" aria-hidden="true">
      {n}
    </span>
  );
}

function Status({ state }: { state: StepState }) {
  if (state === "later") return null;
  return <span className="step-status">{state === "done" ? "Done" : "Next"}</span>;
}

export function HomePage({ profile, source }: HomePageProps) {
  const hasProfile = source !== "example";
  const screened = source === "screening";
  const steps: StepState[] = hasProfile ? ["done", "done", "next"] : ["next", "later", "later"];

  return (
    <div className="home">
      <section className="home-intro">
        <h1>
          {hasProfile ? `Your profile: ${profileLabel(profile)}` : "Start with the screening."}
        </h1>
        <p className="home-lede">
          {hasProfile
            ? "ChromaFix recolors photos and your webcam view for this profile. You can retake the screening or change it by hand at any time."
            : "A short set of dot plates estimates your type of color vision deficiency and how strong it is. Everything else in ChromaFix is tuned to that result."}
        </p>
        <div className="toolbar">
          {hasProfile ? (
            <>
              <a className="button primary button-lg" href={routeHref("images")}>
                Recolor an image
              </a>
              <a className="button button-lg" href={routeHref("live")}>
                Open live webcam
              </a>
            </>
          ) : (
            <>
              <a className="button primary button-lg" href={routeHref("screening")}>
                Start screening
              </a>
              <a className="button button-lg" href={routeHref("games")}>
                I have a participant ID
              </a>
            </>
          )}
        </div>
        <p className="muted">
          The result is an estimate from a class research project. It is not a medical diagnosis.
        </p>
      </section>

      <ol className="home-steps" aria-label="How ChromaFix works">
        <li data-state={steps[0]}>
          <StepMark n={1} state={steps[0]!} />
          <div className="step-body">
            <div className="step-head">
              <a href={routeHref("screening")}>{screened ? "Retake screening" : "Screening"}</a>
              <Status state={steps[0]!} />
            </div>
            <p>24 dot plates. Type the number you see, or say you see none.</p>
          </div>
        </li>
        <li data-state={steps[1]}>
          <StepMark n={2} state={steps[1]!} />
          <div className="step-body">
            <div className="step-head">
              <a href={routeHref("profile")}>Your profile</a>
              <Status state={steps[1]!} />
            </div>
            <p>
              {hasProfile
                ? `${profileLabel(profile)} · ${source === "manual" ? "set by hand" : "from screening"}`
                : "Type (protan, deutan, tritan or normal) and severity from 0 to 1."}
            </p>
          </div>
        </li>
        <li data-state={steps[2]}>
          <StepMark n={3} state={steps[2]!} />
          <div className="step-body">
            <div className="step-head">
              <span className="step-title">Recolor</span>
              <Status state={steps[2]!} />
            </div>
            <p>
              Upload an <a href={routeHref("images")}>image</a> or turn on your{" "}
              <a href={routeHref("live")}>webcam</a>. Colors are adjusted for your profile.
            </p>
          </div>
        </li>
      </ol>
    </div>
  );
}
